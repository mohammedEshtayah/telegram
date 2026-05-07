"""Build HTML captions from source messages (duplicate notice + reply + noise strip)."""

from __future__ import annotations

import html
from typing import Any

from app.utils.telegram_text import strip_known_noise

from .constants import MAX_DUP_EMBED_CHARS
from .log import log

# Telegram HTML has no real background colors. <blockquote> uses the accent stripe (often red/pink).
# We avoid blockquote and use yellow-square bands + <pre> for a neutral “panel” look.

_YELLOW_BAR = "🟨" * 13


def _duplicate_confirmation_html(prev_plain: str) -> str:
    """Duplicate notice: yellow bands, no blockquote (no red accent bar)."""
    escaped_body = html.escape(prev_plain)
    banner = (
        f"{_YELLOW_BAR}\n"
        f"<blockquote>🔁 <i>ADDITIONAL SOURCE</i></blockquote>\n"
        f"<pre>{escaped_body}</pre>"
    )
    return banner


async def clean_message_text(pipeline: Any, event, target_chat_id: int) -> str:
    log("clean_message_text", "info", "start")
    message_text = (event.message.text or "").strip()

    if message_text and pipeline.forward_duplicate_messages:
        match = pipeline.duplicate_match(message_text, target_chat_id)
        if match:
            prev = strip_known_noise(match.get("text") or "")
            if len(prev) > MAX_DUP_EMBED_CHARS:
                prev = prev[:MAX_DUP_EMBED_CHARS].rstrip() + "\n..."
            log("clean_message_text", "ok", "compact_duplicate_confirm")
            return _duplicate_confirmation_html(prev)

    full_caption = ""
    if event.message.is_reply:
        replied_msg = await event.message.get_reply_message()
        if replied_msg and replied_msg.text:
            reply_txt = replied_msg.text.strip()
            escaped_reply = html.escape(reply_txt + "\n=====>")
            full_caption += (
                f"<blockquote>🧾 <b>Reply to:</b></blockquote>\n"
                f"<pre>{escaped_reply}</pre>"
            )
    if message_text:
        full_caption += f"\n{html.escape(message_text)}"
    if not full_caption:
        return ""

    full_caption = strip_known_noise(full_caption)
    log("clean_message_text", "ok", f"caption_chars={len(full_caption)}")
    return full_caption
