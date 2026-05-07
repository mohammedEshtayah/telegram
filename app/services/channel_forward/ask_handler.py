"""Handle /ask against the archived news DB."""

from __future__ import annotations

import re
from typing import Any

from app.services.qa_service import answer_from_stored_news, split_telegram

from .log import log


async def handle_ask(pipeline: Any, event) -> None:
    log("ask_from_archive", "info", "start")
    if not event.text:
        log("ask_from_archive", "fail", "no text")
        return
    t = event.text.strip()

    me = await event.client.get_me()
    allowed_chat_ids = {me.id, pipeline.target_channel, pipeline.target_channel_streets}

    cmd_dup = re.match(r"^/d\s*$", t, re.I)
    cmd_undeplh = re.match(r"^/und\s*$", t, re.I)
    if cmd_dup or cmd_undeplh:
        if event.chat_id not in allowed_chat_ids:
            log("dup_toggle", "fail", f"chat_id not allowed: {event.chat_id}")
            return
        if event.chat_id != me.id and not event.out:
            log("dup_toggle", "fail", "message is not outgoing from this account")
            return
        if cmd_dup:
            pipeline.forward_duplicate_messages = True
            await event.reply(
                "/d: duplicate posts will be forwarded like any other message."
            )
            log("dup_toggle", "ok", "forward_duplicate_messages=True")
        else:
            pipeline.forward_duplicate_messages = False
            await event.reply(
                "/und: duplicate posts will not be forwarded (skipped)."
            )
            log("dup_toggle", "ok", "forward_duplicate_messages=False")
        return

    m = re.match(r"^/ask(\s+|$)(.*)$", t, re.I | re.DOTALL)
    if not m:
        return
    rest = (m.group(2) or "").strip()
    if event.chat_id not in allowed_chat_ids:
        log("ask_from_archive", "fail", f"chat_id not allowed: {event.chat_id}")
        return
    if event.chat_id != me.id and not event.out:
        log("ask_from_archive", "fail", "message is not outgoing from this account")
        return
    if not rest:
        await event.reply(
            "Usage: /ask followed by your question.\n"
            "Examples:\n"
            "• /ask What are the latest stored items about Gaza?\n"
            "• /ask لخصّلي أحداث أمس\n"
            "• /ask اليوم من الصباح حتى الظهر ماذا حدث؟\n"
            "• /ask خلال ساعتين ما بين 2 و 4 ماذا حدث؟\n"
            "Time phrases use ASK_TIMEZONE in .env (default Asia/Jerusalem).\n"
            "Works in Saved Messages or allowed channels."
        )
        log("ask_from_archive", "info", "no rest")
        return
    try:
        log("ask_from_archive", "info", "calling answer_from_stored_news")
        ans = await answer_from_stored_news(rest)
        first = True
        parts_sent = 0
        for part in split_telegram(ans, 4000):
            if not part:
                log("ask_from_archive", "info", "no part")
                continue
            if first:
                await event.reply(part)
                log("ask_from_archive", "info", "first part sent")
                first = False
            else:
                await event.client.send_message(event.chat_id, part)
            parts_sent += 1
        log("ask_from_archive", "ok", f"reply_parts={parts_sent}")
    except Exception as e:
        log("ask_from_archive", "fail", str(e))
        print(f"❌ /ask error: {e}")
        await event.reply(f"Could not generate an answer: {e}")
