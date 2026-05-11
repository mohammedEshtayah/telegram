"""Normalize news text for SQLite storage, captions, and duplicate matching."""

from __future__ import annotations

import re
import unicodedata

# Arabic “breaking” label often prepended to headlines.
_URGENT_MARKER = "عاجل"

# Channel watermark hashtag as Unicode escapes (ASCII-only source).
_NOISE_HASHTAG = (
    "#\u0641\u0644\u0633\u0640\u0640\u0640\U00013086\u0640\u0640\u0640\u0640\u0640\u0640"
    "\u0637\u064a\u0646_\u0627\u0644\u0623\u0642\u0635\u0649 \U0001f1f5\U0001f1f8"
)

# Extra graphic / emoji ranges not always classified as So consistently across Unicode versions.
_EMOJI_BLOCKS = (
    (0x1F300, 0x1FAFF),
    (0x2600, 0x26FF),
    (0x2700, 0x27BF),
    (0x231A, 0x231B),
    (0x23E9, 0x23F3),
    (0x23F8, 0x23FA),
    (0x25AA, 0x25AB),
    (0x25B6, 0x25C0),
    (0x25FB, 0x25FE),
    (0xFE00, 0xFE0F),
)


def strip_known_noise(text: str) -> str:
    """Remove fixed channel watermarks and noise links (safe for HTML captions)."""
    cleaned = (text or "").replace("*", "")
    cleaned = cleaned.replace("https://t.me/Almustashaar", "")
    cleaned = cleaned.replace("https://t.me/+tQHLyywTho82Njky", "")
    cleaned = cleaned.replace("#فلســ𓂆ـــــــــــطين_الأقصى🇵🇸", "")
    cleaned = cleaned.replace(_NOISE_HASHTAG, "")
    return cleaned.strip()


def _is_emoji_codepoint(o: int) -> bool:
    if any(a <= o <= b for a, b in _EMOJI_BLOCKS):
        return True
    if 0x1F1E6 <= o <= 0x1F1FF:
        return True
    return False


def normalize_news_plain(s: str) -> str:
    """strip_known_noise + NFKC; drop عاجل; strip punctuation (except #) and emoji-like symbols; one space."""
    s = strip_known_noise(s or "")
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(_URGENT_MARKER, "")
    out: list[str] = []
    for ch in s:
        o = ord(ch)
        cat = unicodedata.category(ch)
        if cat.startswith("P") and ch != "#":
            continue
        if cat == "So" or _is_emoji_codepoint(o):
            continue
        out.append(ch)
    s = "".join(out)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE)
    return s.strip()
