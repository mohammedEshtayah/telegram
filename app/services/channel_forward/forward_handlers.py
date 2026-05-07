"""Route source chats to main vs Streets targets; forward media and text."""

from __future__ import annotations

from typing import Any

from telethon.tl.types import Channel, Chat, User

from app.db.storage import persist_from_caption

from . import caption, media
from .helpers import first_sent_message_id, group_source_text
from .log import log


def _cleanup_group(pipeline: Any, gid: str) -> None:
    pipeline.dic_count_group.pop(gid, None)
    pipeline.dic_message.pop(gid, None)
    pipeline.dic_group_dup_confirm.pop(gid, None)


async def handle_forward_dispatch(pipeline: Any, event) -> None:
    try:
        log("forward_handler", "info", f"chat_id={event.chat_id}")
        chat = await event.get_chat()
        if isinstance(chat, Channel):
            if chat.megagroup:
                log("forward_handler", "info", f"type=megagroup title={chat.title}")
                await forward_to_streets(pipeline, event, chat)
            else:
                log("forward_handler", "info", f"type=channel title={chat.title}")
                await forward_to_main(pipeline, event, chat)
        elif isinstance(chat, Chat):
            print(f"👥 Message from BASIC GROUP: {chat.title} (ID: {chat.id})")

        elif isinstance(chat, User):
            print(f"👤 Message from PRIVATE CHAT: {chat.first_name} (ID: {chat.id})")
    except Exception as e:
        log("forward_handler", "fail", str(e))
        print(f"❌ Forward error: {e}\n")


async def forward_to_main(pipeline: Any, event, chat) -> None:
    client = pipeline.client
    display_name = chat.title if hasattr(chat, "title") else "Unknown channel"
    log("forward_handler_Channel", "info", f"source={display_name}")
    src_plain = (event.message.text or "").strip()
    tgt = pipeline.target_channel

    is_dup = bool(src_plain) and pipeline.duplicate_match(src_plain, tgt) is not None
    skip_dup = is_dup and not pipeline.forward_duplicate_messages

    if skip_dup and not event.message.grouped_id:
        log("forward_handler_Channel", "info", "skip duplicate (single)")
        print(f"⏭️ Skipped duplicate from {display_name}")
        return

    full_caption = f"<b> 📢 {display_name}</b> \n\n"
    full_caption += await caption.clean_message_text(pipeline, event, tgt)

    if event.message.grouped_id:
        messages = await client.get_messages(event.chat_id, limit=20)
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]
        gid = f"{event.message.grouped_id}"
        if event.message.text != "":
            pipeline.dic_message[gid] = full_caption
            pipeline.dic_group_dup_confirm[gid] = is_dup
        if gid not in pipeline.dic_count_group:
            pipeline.dic_count_group[gid] = 1
        else:
            pipeline.dic_count_group[gid] += 1

        if pipeline.dic_count_group[gid] == len(media_group):
            files = []
            for msg in media_group:
                if msg.media:
                    files.append(msg)
            cap = pipeline.dic_message.get(gid, full_caption)
            group_dup = pipeline.dic_group_dup_confirm.get(gid, False)
            skip_group = group_dup and not pipeline.forward_duplicate_messages
            if files:
                log(
                    "forward_handler_Channel",
                    "info",
                    f"group_media_files={len(files)} group_dup={group_dup} skip_group={skip_group}",
                )
                if skip_group:
                    log("forward_handler_Channel", "info", "skip duplicate (album)")
                    print(f"⏭️ Skipped duplicate album from {display_name}")
                else:
                    mid = await media.download_and_send_media(
                        pipeline,
                        event,
                        cap,
                        files,
                        tgt,
                        archive_info=(display_name, "main"),
                    )
                    gtxt = group_source_text(media_group)
                    if gtxt and mid:
                        pipeline.add_to_recent(gtxt, tgt, mid)
            _cleanup_group(pipeline, gid)

    elif event.message.media:
        log("forward_handler_Channel", "info", "single media message")
        mid = await media.download_and_send_media(
            pipeline,
            event,
            full_caption,
            [event.message],
            tgt,
            archive_info=(display_name, "main"),
        )
        if src_plain and mid:
            pipeline.add_to_recent(src_plain, tgt, mid)
    else:
        log("forward_handler_Channel", "info", "text-only message")
        sent = await client.send_message(
            tgt,
            full_caption,
            parse_mode="html",
        )
        persist_from_caption(full_caption, display_name, "main")
        log("persist_from_caption", "ok", f"source={display_name} stream=main")
        mid = first_sent_message_id(sent)
        if src_plain and mid:
            pipeline.add_to_recent(src_plain, tgt, mid)

    print(f"✅ Forwarded message from {display_name}")


async def forward_to_streets(pipeline: Any, event, chat) -> None:
    client = pipeline.client
    display_name = chat.title if hasattr(chat, "title") else "Unknown channel"
    log("forward_handler_Streets", "info", f"source={display_name}")
    src_plain = (event.message.text or "").strip()
    tgt = pipeline.target_channel_streets

    is_dup = bool(src_plain) and pipeline.duplicate_match(src_plain, tgt) is not None
    #skip_dup = is_dup and not pipeline.forward_duplicate_messages

    #if skip_dup and not event.message.grouped_id:
    #    log("forward_handler_Streets", "info", "skip duplicate (single)")
    #    print(f"⏭️ Skipped duplicate from {display_name} (streets)")
    #    return

    full_caption = await caption.clean_message_text(pipeline, event, tgt)

    if event.message.grouped_id:
        messages = await client.get_messages(event.chat_id, limit=20)
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]
        gid = f"{event.message.grouped_id}"
        if event.message.text != "":
            pipeline.dic_message[gid] = full_caption
            pipeline.dic_group_dup_confirm[gid] = is_dup
        if gid not in pipeline.dic_count_group:
            pipeline.dic_count_group[gid] = 1
        else:
            pipeline.dic_count_group[gid] += 1

        if pipeline.dic_count_group[gid] == len(media_group):
            files = []
            for msg in media_group:
                if msg.media:
                    files.append(msg)
            cap = pipeline.dic_message.get(gid, full_caption)
            group_dup = pipeline.dic_group_dup_confirm.get(gid, False)
            skip_group = group_dup and not pipeline.forward_duplicate_messages
            if files:
                log(
                    "forward_handler_Streets",
                    "info",
                    f"group_media_files={len(files)} group_dup={group_dup} skip_group={skip_group}",
                )
                if skip_group:
                    log("forward_handler_Streets", "info", "skip duplicate (album)")
                    print(f"⏭️ Skipped duplicate album from {display_name} (streets)")
                else:
                    mid = await media.download_and_send_media(
                        pipeline,
                        event,
                        cap,
                        files,
                        tgt,
                        archive_info=(display_name, "streets"),
                    )
                    gtxt = group_source_text(media_group)
                    if gtxt and mid:
                        pipeline.add_to_recent(gtxt, tgt, mid)
            _cleanup_group(pipeline, gid)

    elif event.message.media:
        log("forward_handler_Streets", "info", "single media message")
        mid = await media.download_and_send_media(
            pipeline,
            event,
            full_caption,
            [event.message],
            tgt,
            archive_info=(display_name, "streets"),
        )
        if src_plain and mid:
            pipeline.add_to_recent(src_plain, tgt, mid)
    else:
        log("forward_handler_Streets", "info", "text-only message")
        sent = await client.send_message(
            tgt,
            full_caption,
            parse_mode="html",
        )
        persist_from_caption(full_caption, display_name, "streets")
        log("persist_from_caption", "ok", f"source={display_name} stream=streets")
        mid = first_sent_message_id(sent)
        if src_plain and mid:
            pipeline.add_to_recent(src_plain, tgt, mid)

    print(f"✅ Forwarded message from {display_name}")
