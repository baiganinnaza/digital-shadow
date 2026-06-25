"""
RQ worker function: takes a raw_post_id, runs the full pipeline.
"""
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def process_post(post_id: int):
    """Entry point for RQ job. Runs synchronously (RQ workers are sync)."""
    import asyncio
    asyncio.run(_async_process(post_id))


async def _async_process(post_id: int):
    from sqlalchemy import select
    from app.db import AsyncSessionLocal, get_neo4j_driver
    from app.models import RawPost, Entity, Object, RiskSignal
    from app.processing.extract import extract
    from app.linking.resolve import resolve_entities
    from app.linking.graph import upsert_node, upsert_edge
    from app.risk.rules import calculate_risk

    # Load classifier lazily (model may not exist at import time)
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from ml.classifier import Classifier
    from app.config import settings as _settings
    settings = _settings
    clf = Classifier.get()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RawPost).where(RawPost.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            logger.warning(f"Post {post_id} not found")
            return

        # 1. Extract entities
        extracted = extract(post.text)

        saved_entities = []
        for e in extracted:
            entity = Entity(
                post_id=post.id,
                type=e.type,
                value=e.value,
                confidence=e.confidence,
            )
            db.add(entity)
            try:
                await db.flush()
                saved_entities.append(entity)
            except Exception:
                await db.rollback()

        # 2. Classify
        clf_result = clf.classify(post.text)
        logger.info(f"Post {post_id}: category={clf_result['category']} sale={clf_result['is_illegal_sale']}")

        # 3. Resolve entities → objects
        objects = await resolve_entities(db, post, saved_entities)

        await db.commit()

        # 4. Write to Neo4j graph
        driver = get_neo4j_driver()
        try:
            with driver.session() as session:
                for obj in objects:
                    upsert_node(session, obj.key, obj.type, risk=0.0)
                upsert_edge_pairs(session, objects, saved_entities)
        finally:
            driver.close()

        # 5. Risk scoring — per object
        new_signals = []
        async with AsyncSessionLocal() as db2:
            for obj in objects:
                risk = await calculate_risk(db2, obj, saved_entities, clf_result)
                signal = RiskSignal(
                    object_id=obj.id,
                    score=risk["score"],
                    reasons=risk["reasons"],
                    category=clf_result["category"],
                )
                db2.add(signal)
                await db2.flush()
                if risk["flagged"]:
                    new_signals.append({
                        "type":     "new_signal",
                        "id":       signal.id,
                        "category": clf_result["category"],
                        "score":    round(risk["score"], 3),
                        "object":   obj.key,
                        "source":   post.source,
                    })
            await db2.commit()

        # Publish to Redis → WebSocket clients
        if new_signals:
            import json
            try:
                from redis import Redis
                r = Redis.from_url(settings.redis_url)
                for payload in new_signals:
                    r.publish("new_signal", json.dumps(payload))
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")

        logger.info(f"Post {post_id} processed: {len(objects)} objects, {len(saved_entities)} entities")


def upsert_edge_pairs(session, objects, entities):
    from app.linking.graph import upsert_edge
    # wallet → channel edges
    wallets = [e for e in entities if e.type == "wallet"]
    channels = [e for e in entities if e.type in ("username", "channel")]
    for w in wallets:
        for c in channels:
            w_obj = next((o for o in objects if o.key == w.value), None)
            c_obj = next((o for o in objects if o.key == c.value), None)
            if w_obj and c_obj:
                upsert_edge(session, c_obj.key, w_obj.key, "PAYS_TO", {"reason": "same_post"})
