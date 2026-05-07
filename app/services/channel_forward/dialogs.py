"""Debug: print dialog list after login."""

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, User


async def print_dialogs_snapshot(client: TelegramClient) -> None:
    try:
        dialogs = await client.get_dialogs()
        for dialog in dialogs:
            if dialog.is_channel:
                print(f"📢 {dialog.name} -> ID: {dialog.id}")
            ent = dialog.entity
            if isinstance(ent, Channel):
                if ent.megagroup:
                    title = getattr(dialog, "title", getattr(ent, "title", ""))
                    print(f"📢 Message from SUPERGROUP: {title} (ID: {dialog.id})")
                else:
                    title = getattr(dialog, "title", getattr(ent, "title", ""))
                    print(f"👥 Message from BASIC Channel: {title} (ID: {dialog.id})")

            elif isinstance(ent, Chat):
                title = getattr(ent, "title", "")
                print(f"👥 Message from BASIC GROUP: {title} (ID: {dialog.id})")

            elif isinstance(ent, User):
                name = getattr(ent, "first_name", "") or ""
                print(f"👤 Message from PRIVATE CHAT: {name} (ID: {dialog.id})")

    except Exception as e:
        print(f"❌ Error: {e}")
