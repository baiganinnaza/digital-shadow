"""
Periodic scheduler: puts collection tasks into RQ queue.
Run as: python -m app.scheduler
"""
import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis import Redis
from rq import Queue

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def collect_and_enqueue():
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import RawPost
    from app.processing.worker import process_post
    from app.collectors.seed import SeedCollector
    from app.collectors.telegram_collector import TelegramCollector
    from app.collectors.olx_collector import OlxCollector
    from app.collectors.blockchain_collector import BlockchainCollector

    redis_conn = Redis.from_url(settings.redis_url)
    q = Queue(connection=redis_conn)

    collectors = [SeedCollector(batch_size=10)]
    if settings.use_public_sources:
        collectors.append(TelegramCollector())
        collectors.append(OlxCollector())
        collectors.append(BlockchainCollector())

    posts_data = []
    for collector in collectors:
        try:
            posts_data.extend(collector.fetch())
        except Exception as e:
            logger.error(f"Collector {type(collector).__name__} failed: {e}")

    if not posts_data:
        logger.info("No posts from collectors")
        return

    async with AsyncSessionLocal() as db:
        saved = 0
        for pd in posts_data:
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
            q.enqueue(process_post, post.id)
            saved += 1
        await db.commit()
        logger.info(f"Enqueued {saved} new posts")


async def main_async():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        collect_and_enqueue,
        "interval",
        seconds=settings.collect_interval_sec,
        id="collect",
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"Scheduler started, interval={settings.collect_interval_sec}s")

    await collect_and_enqueue()

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
