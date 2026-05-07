"""Build LLM context and chat messages from retrieved news rows."""

from datetime import datetime, timezone
from typing import List, Optional

from zoneinfo import ZoneInfo

from .config import MAX_CONTEXT_CHARS


def _format_saved_at(iso: str, tz_name: Optional[str]) -> str:
    if not (iso or "").strip():
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if tz_name:
        try:
            local = dt.astimezone(ZoneInfo(tz_name))
            return local.strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            pass
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def format_context(chunks: List[dict], tz_name: Optional[str] = None) -> str:
    parts: List[str] = []
    n = 0
    for ch in chunks:
        n += 1
        src = ch.get("source") or "unknown"
        when = _format_saved_at(ch.get("created_at") or "", tz_name)
        body = (ch.get("text") or "").strip()
        head = f"--- [item {n} | source: {src}"
        if when:
            head += f" | saved: {when}"
        parts.append(f"{head}]\n{body}\n")
    return "\n".join(parts)[:MAX_CONTEXT_CHARS]


def build_messages(context: str, question: str) -> list[dict]:
    sys = (
        "You are an assistant that answers ONLY using the news context below. "
        "Do not use outside knowledge.\n"
        "• If the context relates to the question directly, partially, or by topic, "
        "summarize clearly in sections or paragraphs; do not refuse when there is any relevant tie.\n"
        "• You may combine information from multiple items if they complement each other.\n"
        "• Say the archive does not contain enough only when nothing in the context relates "
        "to the question or could reasonably support an answer.\n"
        "• Do not invent facts or numbers not present in the context.\n"
        "• Reply in the same language as the user's question when possible; "
        "otherwise use clear, neutral English."
    )
    return [
        {"role": "system", "content": sys},
        {
            "role": "user",
            "content": f"News context:\n{context}\n\nQuestion: {question}",
        },
    ]
