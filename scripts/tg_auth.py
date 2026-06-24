"""
One-time Telegram authorization.
Run once to create the session file; after that collectors work automatically.

Usage:
  cd digital-shadow
  python scripts/tg_auth.py

Requires in .env:
  TG_API_ID=...
  TG_API_HASH=...
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings


async def main():
    from telethon import TelegramClient

    if not settings.tg_api_id or not settings.tg_api_hash:
        print("ERROR: TG_API_ID and TG_API_HASH must be set in .env")
        print("Get them at: https://my.telegram.org/apps")
        sys.exit(1)

    session_path = settings.tg_session_path
    Path(session_path).parent.mkdir(parents=True, exist_ok=True)

    client = TelegramClient(session_path, int(settings.tg_api_id), settings.tg_api_hash)

    await client.start()  # interactive: asks phone → code → 2FA if needed

    me = await client.get_me()
    print(f"\nAuthorized as: {me.first_name} (@{me.username})")
    print(f"Session saved to: {session_path}.session")
    print("\nYou can now run the collector with USE_PUBLIC_SOURCES=true")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
