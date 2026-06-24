"""
Collect real data from Telegram + OLX and push through the full pipeline.
Usage: python scripts/collect_real.py
"""
import asyncio, sys, logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from app.config import settings
from app.db import AsyncSessionLocal, engine, Base, get_neo4j_driver
from app.models import RawPost, Entity, Object, RiskSignal
from app.collectors.telegram_collector import TelegramCollector
from app.collectors.olx_collector import OlxCollector
from app.processing.extract import extract
from app.linking.resolve import resolve_entities
from app.linking.graph import upsert_node, upsert_edge
from app.risk.rules import calculate_risk
from ml.classifier import Classifier
from sqlalchemy import select


async def process_post_inline(post: RawPost) -> int:
    clf = Classifier.get()
    async with AsyncSessionLocal() as db:
        extracted = extract(post.text)
        saved_entities = []
        for e in extracted:
            ent = Entity(post_id=post.id, type=e.type, value=e.value, confidence=e.confidence)
            db.add(ent)
            try:
                await db.flush()
                saved_entities.append(ent)
            except Exception:
                await db.rollback()

        clf_result = clf.classify(post.text)
        objects = await resolve_entities(db, post, saved_entities)
        await db.commit()

    driver = get_neo4j_driver()
    try:
        with driver.session() as neo_session:
            for obj in objects:
                upsert_node(neo_session, obj.key, obj.type, risk=0.0)
            wallets = [e for e in saved_entities if e.type == "wallet"]
            accounts = [e for e in saved_entities if e.type == "username"]
            for w in wallets:
                for a in accounts:
                    w_obj = next((o for o in objects if o.key == w.value), None)
                    a_obj = next((o for o in objects if o.key == a.value), None)
                    if w_obj and a_obj:
                        upsert_edge(neo_session, a_obj.key, w_obj.key, "PAYS_TO", {"reason": "same_post"})
    finally:
        driver.close()

    async with AsyncSessionLocal() as db2:
        for obj in objects:
            risk = await calculate_risk(db2, obj, saved_entities, clf_result)
            if risk["score"] > 0:
                signal = RiskSignal(
                    object_id=obj.id,
                    score=risk["score"],
                    reasons=risk["reasons"],
                    category=clf_result["category"],
                )
                db2.add(signal)
        await db2.commit()

    return len(objects)


async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    collectors = [
        ("Telegram", TelegramCollector(limit_per_channel=100)),
        ("OLX", OlxCollector(max_per_keyword=30)),
    ]

    total_new = 0
    for name, collector in collectors:
        print(f"\n[{name}] Fetching...")
        posts_data = collector.fetch()
        print(f"[{name}] Got {len(posts_data)} items")

        async with AsyncSessionLocal() as db:
            for pd in posts_data:
                # Skip duplicates
                if pd.external_id:
                    existing = await db.execute(
                        select(RawPost).where(
                            RawPost.source == pd.source,
                            RawPost.external_id == pd.external_id,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                post = RawPost(
                    source=pd.source,
                    source_url=pd.source_url,
                    external_id=pd.external_id,
                    text=pd.text,
                    collected_at=pd.collected_at,
                    raw=pd.raw,
                )
                db.add(post)
                await db.flush()
                await process_post_inline(post)
                await db.commit()
                total_new += 1
                print(f"  [{pd.source}] processed: {pd.text[:60]}")

    print(f"\nDone. {total_new} new posts processed.")
    print("Open http://localhost:5173 to see results.")


if __name__ == "__main__":
    asyncio.run(main())
