"""
Telegram public channel collector with auto-discovery.
Reads recent messages from configured channels + channels discovered
from t.me/ links found in those messages.

Setup (one-time):
  python scripts/tg_auth.py

Required env vars:
  TG_API_ID, TG_API_HASH, TG_CHANNELS (comma-separated @channel usernames)
"""
import asyncio
import concurrent.futures
import logging
import re
from pathlib import Path

from app.collectors.base import BaseCollector, RawPostData
from app.config import settings

logger = logging.getLogger(__name__)

_TG_LINK = re.compile(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]{3,32})', re.IGNORECASE)
_DISCOVERED_FILE = Path("/app/data/discovered_channels.txt")


class TelegramCollector(BaseCollector):
    def __init__(self, limit_per_channel: int = 100):
        self._limit = limit_per_channel

    def _load_channels(self) -> list[str]:
        seed = [c.strip() for c in settings.tg_channels.split(",") if c.strip()]
        discovered: list[str] = []
        if _DISCOVERED_FILE.exists():
            discovered = [
                ln.strip() for ln in _DISCOVERED_FILE.read_text().splitlines()
                if ln.strip() and ln.strip() not in seed
            ]
            if discovered:
                logger.info(f"TelegramCollector: +{len(discovered)} auto-discovered channels")
        return seed + discovered

    def _save_discovered(self, new_channels: set[str], existing: list[str]) -> None:
        existing_set = {c.lstrip("@").lower() for c in existing}
        to_add = [f"@{c}" for c in new_channels if c.lower() not in existing_set]
        if not to_add:
            return
        _DISCOVERED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _DISCOVERED_FILE.open("a") as f:
            for ch in to_add:
                f.write(ch + "\n")
        logger.info(f"TelegramCollector: discovered {len(to_add)} new channels: {to_add[:5]}")

    def fetch(self) -> list[RawPostData]:
        if not settings.tg_api_id or not settings.tg_api_hash:
            logger.warning("TelegramCollector: TG_API_ID/TG_API_HASH not set, skipping")
            return []
        channels = self._load_channels()
        if not channels:
            logger.warning("TelegramCollector: TG_CHANNELS not set, skipping")
            return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_in_thread, channels)
            try:
                return future.result(timeout=180)
            except Exception as e:
                logger.error(f"TelegramCollector failed: {e}")
                return []

    def _run_in_thread(self, channels: list[str]) -> list[RawPostData]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._fetch_async(channels))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _fetch_async(self, channels: list[str]) -> list[RawPostData]:
        from telethon import TelegramClient
        from telethon.errors import FloodWaitError, ChannelPrivateError
        from datetime import timezone

        from telethon.sessions import StringSession
        session = (
            StringSession(settings.tg_session_string)
            if settings.tg_session_string
            else settings.tg_session_path
        )
        client = TelegramClient(
            session,
            int(settings.tg_api_id),
            settings.tg_api_hash,
        )
        results: list[RawPostData] = []
        discovered_channels: set[str] = set()

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

                        # Auto-discover channels mentioned in messages
                        for match in _TG_LINK.finditer(msg.text):
                            discovered_channels.add(match.group(1).lower())

                    logger.info(f"Telegram: {channel_count} messages from {channel}")
                except ChannelPrivateError:
                    logger.warning(f"Telegram: {channel} is private, skipping")
                except FloodWaitError as e:
                    logger.warning(f"Telegram flood wait {e.seconds}s for {channel}")
                except Exception as e:
                    logger.error(f"Telegram error for {channel}: {e}")
        finally:
            await client.disconnect()

        # Save newly discovered channels for next run
        if discovered_channels:
            self._save_discovered(discovered_channels, channels)

        logger.info(f"TelegramCollector: {len(results)} messages from {len(channels)} channels")
        return results
