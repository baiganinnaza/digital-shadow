"""Check which configured Telegram channels are accessible."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import settings


async def main():
    from telethon import TelegramClient
    from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError, UsernameInvalidError

    channels = [c.strip() for c in settings.tg_channels.split(",") if c.strip()]
    client = TelegramClient(settings.tg_session_path, int(settings.tg_api_id), settings.tg_api_hash)

    await client.connect()
    if not await client.is_user_authorized():
        print("Not authorized. Run: python scripts/tg_auth.py")
        return

    print(f"Checking {len(channels)} channels...\n")
    ok, fail = [], []

    for ch in channels:
        try:
            entity = await client.get_entity(ch)
            members = getattr(entity, "participants_count", "?")
            title = getattr(entity, "title", ch)
            print(f"  OK  {ch:30s}  «{title}»  members={members}")
            ok.append(ch)
        except (ChannelPrivateError,):
            print(f"  PRIVATE  {ch}")
            fail.append(ch)
        except (UsernameNotOccupiedError, UsernameInvalidError):
            print(f"  NOT FOUND  {ch}")
            fail.append(ch)
        except Exception as e:
            print(f"  ERROR  {ch}  — {e}")
            fail.append(ch)

    await client.disconnect()
    print(f"\nAccessible: {len(ok)}, Unavailable: {len(fail)}")


if __name__ == "__main__":
    asyncio.run(main())
