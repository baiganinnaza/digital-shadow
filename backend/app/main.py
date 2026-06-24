from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, text
from pydantic import BaseModel
from typing import Optional
import logging

from app.db import engine, get_db, Base, get_neo4j_driver
from app.models import RawPost, Entity, Object, RiskSignal, Case, Feedback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    yield


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
