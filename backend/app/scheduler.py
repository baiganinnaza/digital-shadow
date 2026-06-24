"""
Periodic scheduler: puts seed collection tasks into RQ queue.
Run as: python -m app.scheduler
"""
import asyncio
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from redis import Redis
from rq import Queue

from app.config import settings
from app.collectors.seed import SeedCollector
from app.collectors.telegram_collector import TelegramCollector
from app.collectors.olx_collector import OlxCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def collect_and_enqueue():
    import asyncio
    asyncio.run(_collect())


async def _collect():
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import RawPost
    from app.processing.worker import process_post

    redis_conn = Redis.from_url(settings.redis_url)
    q = Queue(connection=redis_conn)

    collectors = [SeedCollector(batch_size=10)]
    if settings.use_public_sources:
        collectors.append(TelegramCollector())
        collectors.append(OlxCollector())

    posts_data = []
    for collector in collectors:
        posts_data.extend(collector.fetch())

    if not posts_data:
        logger.info("No posts from collector")
        return

    async with AsyncSessionLocal() as db:
        for pd in posts_data:
            existing = await db.execute(
                select(RawPost).where(
                    RawPost.source == pd.source,
                    RawPost.external_id == pd.external_id,
                )
            )
            if pd.external_id and existing.scalar_one_or_none():
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
            logger.info(f"Enqueued post {post.id}")
        await db.commit()


def main():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        collect_and_enqueue,
        "interval",
        seconds=settings.collect_interval_sec,
        id="seed_collect",
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"Scheduler started, interval={settings.collect_interval_sec}s")

    # Run immediately on start
    collect_and_enqueue()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()
