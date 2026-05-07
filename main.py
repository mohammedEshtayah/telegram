"""Entry point: wire Telethon client, DB init, channel pipeline, run until disconnect."""

from telethon import TelegramClient
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError

from app.config.settings import API_HASH, API_ID, PHONE, SESSION_NAME
from app.db.storage import init_db
from app.services.channel_forward_service import ChannelForwardPipeline, print_dialogs_snapshot


async def run_pipeline(client: TelegramClient) -> None:
    ChannelForwardPipeline(client).register()

    try:
        await client.start(PHONE)
    except AuthKeyDuplicatedError:
        print(
            "❌ Telethon session is invalid (AuthKeyDuplicatedError).\n"
            "Fix:\n"
            "1) Set SESSION_NAME in .env to a new value (e.g. forward_bot_session_oracle).\n"
            "2) Restart the bot and complete Telegram login once.\n"
            "3) Do not use the same session file on two devices at the same time."
        )
        return

    init_db()
    await print_dialogs_snapshot(client)
    print("🤖 Bot running; listening to channels...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    _client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    _client.loop.run_until_complete(run_pipeline(_client))
