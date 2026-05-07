"""Build LLM context and chat messages from retrieved news rows."""

from typing import List

from .config import MAX_CONTEXT_CHARS


def format_context(chunks: List[dict]) -> str:
    parts: List[str] = []
    n = 0
    for ch in chunks:
        n += 1
        src = ch.get("source") or "unknown"
        body = (ch.get("text") or "").strip()
        parts.append(f"--- [item {n} | source: {src}]\n{body}\n")
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
