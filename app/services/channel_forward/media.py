"""Download media from source messages and post to target channels."""

from __future__ import annotations

import os
from typing import Any

from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

from app.db.storage import persist_from_caption

from .helpers import first_sent_message_id
from .log import log


async def download_and_send_media(
    pipeline: Any,
    event,
    caption: str,
    files: list,
    channel_id: int,
    archive_info: tuple[str, str] | None = None,
) -> int | None:
    sent_msg_id: int | None = None
    client = pipeline.client
    try:
        log("download_and_send_media", "info", f"target={channel_id} files_in={len(files)}")
        temp_files = []
        for media_msg in files:
            if isinstance(media_msg.media, (MessageMediaPhoto, MessageMediaDocument)):
                temp_file = await client.download_media(media_msg.media)
                temp_files.append(temp_file)

        if temp_files:
            result = await client.send_file(
                channel_id,
                temp_files,
                caption=caption,
                parse_mode="html",
            )
            sent_msg_id = first_sent_message_id(result)
        else:
            result = await client.send_message(
                channel_id,
                message=caption,
                parse_mode="html",
            )
            sent_msg_id = first_sent_message_id(result)
        if archive_info:
            persist_from_caption(caption, archive_info[0], archive_info[1])
            log(
                "persist_from_caption",
                "ok",
                f"source={archive_info[0]} stream={archive_info[1]}",
            )
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        log(
            "download_and_send_media",
            "ok",
            f"sent_files={len(temp_files)} msg_id={sent_msg_id}",
        )

    except Exception as e:
        log("download_and_send_media", "fail", str(e))
        print(f"❌ Error downloading or sending media: {e}")
    return sent_msg_id
