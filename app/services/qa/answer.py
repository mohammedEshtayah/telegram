"""Orchestrate search + LLM completion for /ask."""

from app.db.storage import search_relevant

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

    rows = search_relevant(q, limit=45)
    if not rows:
        log("search_relevant", "fail", "no rows in DB")
        return (
            "No archived news yet. Wait until messages are collected from channels, "
            "then try /ask again."
        )
    log("search_relevant", "ok", f"rows={len(rows)}")

    ctx = format_context(rows)
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
