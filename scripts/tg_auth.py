"""
One-time Telegram session setup. Run LOCALLY (not in Docker):
    pip install telethon
    python scripts/tg_auth.py

Get API_ID and API_HASH at https://my.telegram.org/apps
Copy the output TG_SESSION_STRING into your .env file.
"""
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

print("=== Digital Shadow — Telegram Session Setup ===\n")
print("Получи credentials на https://my.telegram.org/apps\n")

api_id   = int(input("API_ID:   "))
api_hash = input("API_HASH: ").strip()
phone    = input("Номер телефона (+77001234567): ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    client.start(phone=phone)
    session_string = client.session.save()

print("\n✅ Авторизация прошла успешно!\n")
print("Добавь в .env файл следующие строки:\n")
print(f"TG_API_ID={api_id}")
print(f"TG_API_HASH={api_hash}")
print(f"TG_SESSION_STRING={session_string}")
