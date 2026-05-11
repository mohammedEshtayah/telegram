"""Route source chats to main vs Streets targets; forward media and text."""

from __future__ import annotations

from typing import Any, Literal

from telethon.tl.types import Channel, Chat, User

from app.db.storage import persist_from_caption

from . import caption, media
from .helpers import first_sent_message_id, group_source_text
from .log import log

Stream = Literal["main", "streets"]


def _cleanup_group(pipeline: Any, gid: str) -> None:
    pipeline.dic_count_group.pop(gid, None)
    pipeline.dic_message.pop(gid, None)


def _is_duplicate(pipeline: Any, body: str, target_chat_id: int) -> bool:
    return bool(body) and pipeline.duplicate_match(body, target_chat_id) is not None


async def handle_forward_dispatch(pipeline: Any, event) -> None:
    try:
        log("forward_handler", "info", f"chat_id={event.chat_id}")
        chat = await event.get_chat()
        if isinstance(chat, Channel):
            if chat.megagroup:
                log("forward_handler", "info", f"type=megagroup title={chat.title}")
                await _forward_to_target(pipeline, event, chat, stream="streets")
            else:
                log("forward_handler", "info", f"type=channel title={chat.title}")
                await _forward_to_target(pipeline, event, chat, stream="main")
        elif isinstance(chat, Chat):
            print(f"👥 Message from BASIC GROUP: {chat.title} (ID: {chat.id})")

        elif isinstance(chat, User):
            print(f"👤 Message from PRIVATE CHAT: {chat.first_name} (ID: {chat.id})")
    except Exception as e:
        log("forward_handler", "fail", str(e))
        print(f"❌ Forward error: {e}\n")


async def _forward_to_target(pipeline: Any, event, chat, *, stream: Stream) -> None:
    """
    Ordered steps per update:
    1) Resolve target + caption (HTML).
    2) Single message: duplicate check -> optional early exit.
    3) Album: buffer captions; on last piece duplicate check uses full group text -> send or skip.
    4) On send: media helper persists to DB; text-only persists here; then add_to_recent.
    """
    client = pipeline.client
    display_name = chat.title if hasattr(chat, "title") else "Unknown channel"
    tgt = pipeline.target_channel_streets if stream == "streets" else pipeline.target_channel
    log_label = "forward_handler_Streets" if stream == "streets" else "forward_handler_Channel"
    log(log_label, "info", f"source={display_name}")

    inner_caption = await caption.clean_message_text(pipeline, event, tgt)
    if stream == "main":
        full_caption = f"<b> 📢 {display_name}</b> \n\n{inner_caption}"
    else:
        full_caption = inner_caption

    src_plain = (event.message.text or "").strip()
    skip_single = (
        not event.message.grouped_id
        and _is_duplicate(pipeline, src_plain, tgt)
        and not pipeline.forward_duplicate_messages
    )
    if skip_single:
        log(log_label, "info", "skip duplicate (single)")
        print(f"⏭️ Skipped duplicate from {display_name}")
        return

    forwarded = False

    if event.message.grouped_id:
        messages = await client.get_messages(event.chat_id, limit=20)
        media_group = [msg for msg in messages if msg.grouped_id == event.message.grouped_id]
        gid = str(event.message.grouped_id)
        if event.message.text:
            pipeline.dic_message[gid] = full_caption
        pipeline.dic_count_group[gid] = pipeline.dic_count_group.get(gid, 0) + 1

        if pipeline.dic_count_group[gid] == len(media_group):
            files = [msg for msg in media_group if msg.media]
            cap = pipeline.dic_message.get(gid, full_caption)
            gtxt = group_source_text(media_group)
            group_dup = _is_duplicate(pipeline, gtxt, tgt)
            skip_group = group_dup and not pipeline.forward_duplicate_messages
            if files:
                log(
                    log_label,
                    "info",
                    f"group_media_files={len(files)} group_dup={group_dup} skip_group={skip_group}",
                )
                if skip_group:
                    log(log_label, "info", "skip duplicate (album)")
                    print(f"⏭️ Skipped duplicate album from {display_name}")
                else:
                    mid = await media.download_and_send_media(
                        pipeline,
                        event,
                        cap,
                        files,
                        tgt,
                        archive_info=(display_name, stream),
                    )
                    if gtxt and mid:
                        pipeline.add_to_recent(gtxt, tgt, mid)
                    forwarded = True
            _cleanup_group(pipeline, gid)

    elif event.message.media:
        log(log_label, "info", "single media message")
        mid = await media.download_and_send_media(
            pipeline,
            event,
            full_caption,
            [event.message],
            tgt,
            archive_info=(display_name, stream),
        )
        if src_plain and mid:
            pipeline.add_to_recent(src_plain, tgt, mid)
        forwarded = bool(mid)

    else:
        log(log_label, "info", "text-only message")
        sent = await client.send_message(
            tgt,
            full_caption,
            parse_mode="html",
        )
        persist_from_caption(full_caption, display_name, stream)
        log("persist_from_caption", "ok", f"source={display_name} stream={stream}")
        mid = first_sent_message_id(sent)
        if src_plain and mid:
            pipeline.add_to_recent(src_plain, tgt, mid)
        forwarded = mid is not None

    if forwarded:
        print(f"✅ Forwarded message from {display_name}")
