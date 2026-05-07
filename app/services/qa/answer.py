"""Orchestrate search + LLM completion for /ask."""

from app.config.settings import ASK_TIMEZONE
from app.db.storage import search_relevant
from app.utils.ask_time_range import parse_ask_time_range

from .config import log, pick_provider
from . import gemini_client, ollama_client, openai_client
from .prompts import build_messages, format_context


async def answer_from_stored_news(question: str) -> str:
    log("start", "info")
    q = (question or "").strip()
    if not q:
        log("validate_question", "fail", "empty question")
        return "Type your question after /ask"
    log("validate_question", "ok", f"len={len(q)}")

    parsed_time = parse_ask_time_range(q, ASK_TIMEZONE)
    search_q = parsed_time.search_query if parsed_time else q

    prov, cfg = pick_provider()
    if not prov or not cfg:
        log("provider_config", "fail", "missing provider settings in .env")
        return (
            "LLM is not configured. Set one of in .env: "
            "GEMINI_API_KEY (optional GEMINI_MODEL), "
            "OPENAI_API_KEY (optional LLM_MODEL), "
            "OLLAMA_MODEL with Ollama running, "
            "or LLM_PROVIDER=gemini|openai|ollama."
        )
    log("provider_config", "ok", f"provider={prov}")

    rows = search_relevant(
        search_q,
        limit=45,
        window_start_utc=parsed_time.window.start_utc if parsed_time else None,
        window_end_utc=parsed_time.window.end_utc if parsed_time else None,
        window_end_exclusive=parsed_time.window.end_exclusive if parsed_time else True,
    )
    if not rows:
        log("search_relevant", "fail", "no rows in DB")
        if parsed_time:
            return (
                "No archived items in that time window. "
                "Try a wider range, another day, or /ask without a date filter."
            )
        return (
            "No archived news yet. Wait until messages are collected from channels, "
            "then try /ask again."
        )
    log("search_relevant", "ok", f"rows={len(rows)}")

    ctx = format_context(rows, tz_name=ASK_TIMEZONE)
    if not ctx.strip():
        log("build_context", "fail", "empty context after formatting")
        return "Could not build context from the archive. Try a simpler question."
    log("build_context", "ok", f"context_chars={len(ctx)}")

    messages = build_messages(ctx, q)
    log("build_messages", "ok", f"messages={len(messages)}")
    try:
        if prov == "gemini":
            ans = await gemini_client.complete(messages, cfg)
        elif prov == "ollama":
            ans = await ollama_client.complete(messages, cfg)
        else:
            ans = await openai_client.complete(messages, cfg)
        log("generate_answer", "ok", f"answer_chars={len(ans.strip())}")
        return ans
    except Exception as e:
        log("generate_answer", "fail", str(e))
        raise
