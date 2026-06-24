"""
One-shot seed loader: sends all seed_posts.jsonl through the full pipeline.
Usage (from project root): python scripts/seed.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.db import AsyncSessionLocal, engine, Base
from app.models import RawPost
from app.processing.worker import process_post


async def main():
    seed_path = Path(settings.seed_file_path)
    if not seed_path.exists():
        print(f"ERROR: {seed_path} not found. Run: python ml/gen_synthetic.py")
        sys.exit(1)

    posts = []
    with seed_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))

    print(f"Seeding {len(posts)} posts...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        for i, p in enumerate(posts):
            post = RawPost(
                source=p.get("source", "seed:unknown"),
                source_url=p.get("source_url"),
                external_id=p.get("external_id"),
                text=p["text"],
                raw=p,
            )
            db.add(post)
            await db.commit()
            print(f"  [{i+1}/{len(posts)}] Inserted post {post.id}")

            # Process synchronously (no RQ needed for one-shot seed)
            await _process_inline(post.id)

    print("Seed complete.")


async def _process_inline(post_id: int):
    from app.db import AsyncSessionLocal, get_neo4j_driver
    from sqlalchemy import select
    from app.models import RawPost, Entity, Object, RiskSignal
    from app.processing.extract import extract
    from app.linking.resolve import resolve_entities
    from app.linking.graph import upsert_node, upsert_edge
    from app.risk.rules import calculate_risk
    from ml.classifier import Classifier

    clf = Classifier.get()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RawPost).where(RawPost.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            return

        extracted = extract(post.text)
        saved_entities = []
        for e in extracted:
            entity = Entity(post_id=post.id, type=e.type, value=e.value, confidence=e.confidence)
            db.add(entity)
            try:
                await db.flush()
                saved_entities.append(entity)
            except Exception:
                await db.rollback()

        clf_result = clf.classify(post.text)
        objects = await resolve_entities(db, post, saved_entities)
        await db.commit()

        driver = get_neo4j_driver()
        try:
            with driver.session() as session:
                for obj in objects:
                    upsert_node(session, obj.key, obj.type, risk=0.0)
                # wallet → account edges
                wallets = [e for e in saved_entities if e.type == "wallet"]
                accounts = [e for e in saved_entities if e.type == "username"]
                for w in wallets:
                    for a in accounts:
                        w_obj = next((o for o in objects if o.key == w.value), None)
                        a_obj = next((o for o in objects if o.key == a.value), None)
                        if w_obj and a_obj:
                            upsert_edge(session, a_obj.key, w_obj.key, "PAYS_TO", {"reason": "same_post"})
        finally:
            driver.close()

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
            await db2.commit()


if __name__ == "__main__":
    asyncio.run(main())
