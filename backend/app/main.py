from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, text, func
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import logging

from app.db import engine, get_db, Base, get_neo4j_driver
from app.models import RawPost, Entity, Object, RiskSignal, Case, Feedback
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── WebSocket manager ────────────────────────────────────────────────────────

class WSManager:
    def __init__(self):
        self._clients: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    async def broadcast(self, data: dict):
        dead = []
        for ws in self._clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = WSManager()


async def _redis_relay():
    """Listen to Redis pub/sub and relay new signals to WebSocket clients."""
    try:
        from redis.asyncio import Redis as ARedis
        r = ARedis.from_url(settings.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe("new_signal")
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await ws_manager.broadcast(data)
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Redis relay stopped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    relay_task = asyncio.create_task(_redis_relay())
    yield
    relay_task.cancel()


app = FastAPI(title="Digital Shadow API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── Signals ─────────────────────────────────────────────────────────────────

@app.get("/api/signals")
async def list_signals(
    sort: str = Query("risk_desc"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(RiskSignal, Object)
        .join(Object, RiskSignal.object_id == Object.id)
        .where(RiskSignal.status != "dismissed")
    )
    if sort == "risk_desc":
        stmt = stmt.order_by(desc(RiskSignal.score))
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": sig.id,
            "object_id": obj.id,
            "object_key": obj.key,
            "type": obj.type,
            "score": sig.score,
            "category": sig.category,
            "reasons": sig.reasons,
            "created_at": sig.created_at.isoformat(),
            "status": sig.status,
        }
        for sig, obj in rows
    ]


class DismissResponse(BaseModel):
    ok: bool


@app.post("/api/signals/{signal_id}/dismiss", response_model=DismissResponse)
async def dismiss_signal(signal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RiskSignal).where(RiskSignal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    signal.status = "dismissed"
    await db.commit()
    return {"ok": True}


# ── Objects ──────────────────────────────────────────────────────────────────

@app.get("/api/objects/{object_id}")
async def get_object(object_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    signals_result = await db.execute(
        select(RiskSignal).where(RiskSignal.object_id == object_id).order_by(desc(RiskSignal.score))
    )
    signals = signals_result.scalars().all()

    entities_result = await db.execute(
        select(Entity, RawPost)
        .join(RawPost, Entity.post_id == RawPost.id)
        .join(Object, text(f"'{obj.key}' = ANY(ARRAY[entities.value])"))
        .where(Entity.value == obj.key)
        .limit(50)
    )

    entities_result2 = await db.execute(
        select(Entity).where(Entity.value == obj.key).limit(50)
    )
    entities = entities_result2.scalars().all()

    posts_ids = {e.post_id for e in entities}
    provenance = []
    for pid in list(posts_ids)[:10]:
        post_result = await db.execute(select(RawPost).where(RawPost.id == pid))
        post = post_result.scalar_one_or_none()
        if post:
            provenance.append({
                "source": post.source,
                "source_url": post.source_url,
                "collected_at": post.collected_at.isoformat(),
            })

    return {
        "id": obj.id,
        "key": obj.key,
        "type": obj.type,
        "attrs": obj.attrs,
        "signals": [
            {"id": s.id, "score": s.score, "category": s.category, "reasons": s.reasons, "status": s.status}
            for s in signals
        ],
        "entities": [
            {"type": e.type, "value": e.value, "confidence": e.confidence}
            for e in entities
        ],
        "provenance": provenance,
    }


# ── Graph ────────────────────────────────────────────────────────────────────

@app.get("/api/graph/{object_id}")
async def get_graph(object_id: int, depth: int = Query(2, le=4), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")

    driver = get_neo4j_driver()
    nodes = {}
    edges = []

    try:
        with driver.session() as session:
            cypher = (
                "MATCH p = (o:Object {key:$key})-[:PAYS_TO|LINKED|SAME_AS|POSTED_IN*1.."
                + str(depth)
                + "]-(x:Object) "
                "RETURN p"
            )
            result_graph = session.run(cypher, key=obj.key)
            for record in result_graph:
                path = record["p"]
                for node in path.nodes:
                    nid = str(node.element_id)
                    nodes[nid] = {
                        "id": nid,
                        "key": node.get("key", ""),
                        "type": node.get("type", ""),
                        "risk": node.get("risk", 0.0),
                    }
                for rel in path.relationships:
                    edges.append({
                        "source": str(rel.start_node.element_id),
                        "target": str(rel.end_node.element_id),
                        "type": rel.type,
                        "reason": rel.get("reason", ""),
                    })
    finally:
        driver.close()

    if obj.key not in {n["key"] for n in nodes.values()}:
        nodes["root"] = {"id": "root", "key": obj.key, "type": obj.type, "risk": 0.0}

    return {"nodes": list(nodes.values()), "edges": edges}


# ── Cases ────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str
    object_id: int
    note: Optional[str] = None


@app.post("/api/cases")
async def create_case(body: CaseCreate, db: AsyncSession = Depends(get_db)):
    case = Case(title=body.title, object_id=body.object_id, note=body.note)
    db.add(case)
    await db.flush()
    stmt = update(RiskSignal).where(RiskSignal.object_id == body.object_id, RiskSignal.status == "open").values(status="case")
    await db.execute(stmt)
    await db.commit()
    return {"id": case.id}


@app.get("/api/cases")
async def list_cases(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Case).order_by(desc(Case.created_at)))
    cases = result.scalars().all()
    return [
        {"id": c.id, "title": c.title, "object_id": c.object_id, "note": c.note, "created_at": c.created_at.isoformat()}
        for c in cases
    ]


# ── Feedback ─────────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    signal_id: int
    verdict: str  # 'true_positive' | 'false_positive'


@app.post("/api/feedback")
async def create_feedback(body: FeedbackCreate, db: AsyncSession = Depends(get_db)):
    if body.verdict not in ("true_positive", "false_positive"):
        raise HTTPException(status_code=400, detail="verdict must be true_positive or false_positive")
    fb = Feedback(signal_id=body.signal_id, verdict=body.verdict)
    db.add(fb)
    if body.verdict == "false_positive":
        await db.execute(
            update(RiskSignal).where(RiskSignal.id == body.signal_id).values(status="false_positive")
        )
    await db.commit()
    return {"ok": True}


# ── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/signals")
async def ws_signals(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        while True:
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ── Map aggregation ──────────────────────────────────────────────────────────

KZ_CITY_COORDS: dict[str, tuple[float, float]] = {
    "алматы":           (43.238, 76.945),
    "шымкент":          (42.317, 69.590),
    "астана":           (51.180, 71.446),
    "нур-султан":       (51.180, 71.446),
    "тараз":            (42.900, 71.363),
    "кызылорда":        (44.852, 65.509),
    "актобе":           (50.280, 57.207),
    "атырау":           (47.117, 51.920),
    "актау":            (43.652, 51.157),
    "усть-каменогорск": (49.948, 82.628),
    "оскемен":          (49.948, 82.628),
    "павлодар":         (52.287, 76.967),
    "семей":            (50.411, 80.226),
    "костанай":         (53.214, 63.625),
    "петропавловск":    (54.865, 69.138),
    "уральск":          (51.226, 51.380),
    "талдыкорган":      (45.013, 78.374),
    "кокшетау":         (53.285, 69.392),
}


@app.get("/api/signals/map")
async def get_signals_map(db: AsyncSession = Depends(get_db)):
    """Aggregated signal counts per KZ city for map.html globe."""
    stmt = (
        select(RiskSignal.score, RawPost.text)
        .join(Object, RiskSignal.object_id == Object.id)
        .join(Entity, Entity.value == Object.key)
        .join(RawPost, Entity.post_id == RawPost.id)
        .where(RiskSignal.status != "dismissed")
        .limit(1000)
    )
    rows = (await db.execute(stmt)).all()

    regions: dict[str, dict] = {}
    for score, text in rows:
        text_lower = (text or "").lower()
        for city_key, (lat, lng) in KZ_CITY_COORDS.items():
            if city_key in text_lower:
                if city_key not in regions:
                    regions[city_key] = {
                        "name": city_key.capitalize(),
                        "lat": lat, "lng": lng,
                        "signals": 0, "max_score": 0.0, "risk": "low",
                    }
                r = regions[city_key]
                r["signals"] += 1
                if score > r["max_score"]:
                    r["max_score"] = score
                    r["risk"] = ("critical" if score >= 0.75 else
                                 "high"     if score >= 0.50 else
                                 "medium"   if score >= 0.30 else "low")
                break

    total_cases = (await db.execute(select(func.count(Case.id)))).scalar() or 0
    return {
        "regions":       list(regions.values()),
        "total_signals": sum(r["signals"] for r in regions.values()),
        "total_cases":   total_cases,
    }
