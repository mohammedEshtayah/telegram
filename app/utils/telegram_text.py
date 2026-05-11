"""Helpers for Telegram-oriented text processing."""


def split_telegram(text: str, limit: int = 4000) -> list[str]:
    t = (text or "").replace("\r\n", "\n")
    if len(t) <= limit:
        return [t] if t else [""]
    out: list[str] = []
    s = 0
    while s < len(t):
        out.append(t[s : s + limit])
        s += limit
    return out
