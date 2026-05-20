"""Run once on your PC (where Telegram sends the login code). Copy output into .env as TELEGRAM_STRING_SESSION."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")


async def main() -> None:
    if not API_ID or not API_HASH or not PHONE:
        print("Set API_ID, API_HASH, and PHONE in .env first.")
        sys.exit(1)
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        s = client.session.save()
        print("\n--- Add this line to .env on Oracle (keep secret) ---\n")
        print(f"TELEGRAM_STRING_SESSION={s}")
        print("\n--- End ---\n")


if __name__ == "__main__":
    asyncio.run(main())
