"""
Telegram public channel collector.
Reads recent messages from configured public channels via Telethon.

Setup (one-time):
  python scripts/tg_auth.py

Required env vars:
  TG_API_ID, TG_API_HASH, TG_CHANNELS (comma-separated @channel usernames)
"""
import asyncio
import concurrent.futures
import logging
from datetime import datetime, timezone, timedelta

from app.collectors.base import BaseCollector, RawPostData
from app.config import settings

logger = logging.getLogger(__name__)


class TelegramCollector(BaseCollector):
    def __init__(self, limit_per_channel: int = 100):
        self._limit = limit_per_channel

    def fetch(self) -> list[RawPostData]:
        if not settings.tg_api_id or not settings.tg_api_hash:
            logger.warning("TelegramCollector: TG_API_ID/TG_API_HASH not set, skipping")
            return []
        channels = [c.strip() for c in settings.tg_channels.split(",") if c.strip()]
        if not channels:
            logger.warning("TelegramCollector: TG_CHANNELS not set, skipping")
            return []

        # Run in a dedicated thread with its own event loop to avoid
        # conflicting with the scheduler's asyncio.run() loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_in_thread)
            try:
                return future.result(timeout=120)
            except Exception as e:
                logger.error(f"TelegramCollector failed: {e}")
                return []

    def _run_in_thread(self) -> list[RawPostData]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._fetch_async())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _fetch_async(self) -> list[RawPostData]:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError, ChannelPrivateError
        from datetime import timezone

        channels = [c.strip() for c in settings.tg_channels.split(",") if c.strip()]

        client = TelegramClient(
            settings.tg_session_path,
            int(settings.tg_api_id),
            settings.tg_api_hash,
        )
        results: list[RawPostData] = []

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(
                    "Telegram session not authorized. "
                    "Run: python scripts/tg_auth.py"
                )
                return []

            for channel in channels:
                channel_count = 0
                try:
                    async for msg in client.iter_messages(channel, limit=self._limit):
                        if not msg.text:
                            continue
                        msg_date = msg.date
                        if msg_date.tzinfo is None:
                            msg_date = msg_date.replace(tzinfo=timezone.utc)
                        handle = channel.lstrip("@")
                        results.append(RawPostData(
                            source=f"telegram:{channel}",
                            text=msg.text,
                            external_id=f"{handle}_{msg.id}",
                            source_url=f"https://t.me/{handle}/{msg.id}",
                            collected_at=msg_date,
                            raw={"channel": channel, "message_id": msg.id},
                        ))
                        channel_count += 1
                    logger.info(f"Telegram: {channel_count} messages from {channel}")
                except ChannelPrivateError:
                    logger.warning(f"Telegram: {channel} is private, skipping")
                except FloodWaitError as e:
                    logger.warning(f"Telegram flood wait {e.seconds}s for {channel}")
                except Exception as e:
                    logger.error(f"Telegram error for {channel}: {e}")
        finally:
            await client.disconnect()

        logger.info(f"TelegramCollector: {len(results)} messages from {len(channels)} channels")
        return results
