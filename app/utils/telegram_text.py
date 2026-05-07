"""Helpers for Telegram-oriented text processing."""


# Channel watermark hashtag as Unicode escapes (ASCII-only source).
_NOISE_HASHTAG = (
    "#\u0641\u0644\u0633\u0640\u0640\u0640\U00013086\u0640\u0640\u0640\u0640\u0640\u0640"
    "\u0637\u064a\u0646_\u0627\u0644\u0623\u0642\u0635\u0649 \U0001f1f5\U0001f1f8"
)


def strip_known_noise(text: str) -> str:
    cleaned = (text or "").replace("*", "")
    cleaned = cleaned.replace("https://t.me/Almustashaar", "")
    cleaned = cleaned.replace("https://t.me/+tQHLyywTho82Njky", "")
    cleaned = cleaned.replace(_NOISE_HASHTAG, "")
    return cleaned.strip()


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
