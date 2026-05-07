"""Parse Arabic (and simple English) time phrases in /ask questions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return s.translate(_AR_DIGITS)


@dataclass(frozen=True)
class TimeWindow:
    """UTC bounds for DB filtering. If end_exclusive, SQL uses created_at < end_utc."""

    start_utc: datetime
    end_utc: datetime
    end_exclusive: bool = True


@dataclass(frozen=True)
class ParsedAskTime:
    window: TimeWindow
    """Normalized question with the matched time phrase removed (better keyword search)."""

    search_query: str


def _local_midnight(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time.min, tzinfo=tz)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _combine_local(
    tz: ZoneInfo,
    d: date,
    hour: int,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, second, tzinfo=tz)


def _strip_match(text: str, m: re.Match[str]) -> str:
    a, b = m.span()
    return (text[:a] + " " + text[b:]).strip()


def _infer_meridian_pair(h1: int, h2: int, blob: str) -> str:
    """Return 'am', 'pm', or '24' for two clock hours in 1..12 range."""
    low = blob.casefold()
    if re.search(r"صباح|فجر|صباحا|صباحًا", low):
        return "am"
    if re.search(
        r"مساء|مساءً|مساءا|ليل|ليلا|عصر|عصرا|بعد\s*الظهر",
        low,
    ):
        return "pm"
    mx = max(h1, h2)
    mn = min(h1, h2)
    if mn >= 6 and mx <= 11:
        return "am"
    if mx <= 7:
        return "pm"
    return "pm"


def _to_24h(h: int, meridian: str) -> int:
    if meridian == "24":
        return h % 24
    if meridian == "am":
        if h == 12:
            return 0
        return h
    if h == 12:
        return 12
    return h + 12


def _ordered_hours_local(
    tz: ZoneInfo,
    day: date,
    h1: int,
    m1: int,
    h2: int,
    m2: int,
    meridian: str,
) -> tuple[datetime, datetime]:
    """Interpret two clock readings as start/end today in local tz."""
    a = _combine_local(tz, day, _to_24h(h1, meridian), m1)
    b = _combine_local(tz, day, _to_24h(h2, meridian), m2)
    if b <= a:
        b = b + timedelta(days=1)
    return a, b


_RE_YESTERDAY = re.compile(
    r"(?:أمس|إمس|امس|البارحة|البارحه|يا\s*مس|yesterday|\bams\b)",
    re.I,
)
_RE_TODAY_WORD = re.compile(
    r"(?:اليوم|هذا\s*اليوم|today)",
    re.I,
)
_RE_MORN_NOON = re.compile(
    r"(?:من\s+الصباح\s+حتى\s+الظهر|من\s+الصباح\s+للظهر|من\s+الصباح\s+للظهيرة"
    r"|صباح\s*اليوم\s+حتى\s+الظهر|من\s+الفجر\s+حتى\s+الظهر)",
    re.I,
)
_RE_BETWEEN_HOURS = re.compile(
    r"(?:بين\s+الساعة|من\s+الساعة)\s*(\d{1,2})(?::(\d{2}))?\s*"
    r"(?:و|إلى|الى|ـ|-)\s*(?:الساعة\s*)?(\d{1,2})(?::(\d{2}))?",
    re.I,
)
_RE_BETWEEN_SIMPLE = re.compile(
    r"(?:ما\s*بين|ما\s*بي\s*|من)\s*(\d{1,2})(?::(\d{2}))?\s*(?:و|إلى|الى)\s*(\d{1,2})(?::(\d{2}))?",
    re.I,
)


def _try_yesterday(q: str, tz: ZoneInfo, now_local: datetime) -> ParsedAskTime | None:
    m = _RE_YESTERDAY.search(q)
    if not m:
        return None
    d = now_local.date() - timedelta(days=1)
    start = _local_midnight(d, tz)
    end = _local_midnight(d + timedelta(days=1), tz)
    w = TimeWindow(
        start.astimezone(timezone.utc),
        end.astimezone(timezone.utc),
        end_exclusive=True,
    )
    return ParsedAskTime(w, _strip_match(q, m))


def _try_morning_noon(q: str, tz: ZoneInfo, now_local: datetime) -> ParsedAskTime | None:
    m = _RE_MORN_NOON.search(q)
    if not m:
        return None
    d = now_local.date()
    start = _combine_local(tz, d, 6, 0, 0)
    end = _combine_local(tz, d, 12, 0, 0)
    w = TimeWindow(
        start.astimezone(timezone.utc),
        end.astimezone(timezone.utc),
        end_exclusive=True,
    )
    return ParsedAskTime(w, _strip_match(q, m))


def _parse_hour_match(
    m: re.Match[str],
    q: str,
    tz: ZoneInfo,
    now_local: datetime,
) -> ParsedAskTime:
    h1, m1s, h2, m2s = int(m.group(1)), m.group(2), int(m.group(3)), m.group(4)
    mi1 = int(m1s) if m1s else 0
    mi2 = int(m2s) if m2s else 0
    blob = q[max(0, m.start() - 40) : m.end() + 40]
    if h1 > 23 or h2 > 23:
        meridian = "24"
    elif h1 > 12 or h2 > 12:
        meridian = "24"
    else:
        meridian = _infer_meridian_pair(h1, h2, blob)
    day = now_local.date()
    start_l, end_l = _ordered_hours_local(tz, day, h1, mi1, h2, mi2, meridian)
    w = TimeWindow(
        start_l.astimezone(timezone.utc),
        end_l.astimezone(timezone.utc),
        end_exclusive=True,
    )
    return ParsedAskTime(w, _strip_match(q, m))


def _try_between_hours(q: str, tz: ZoneInfo, now_local: datetime) -> ParsedAskTime | None:
    for rx in (_RE_BETWEEN_HOURS, _RE_BETWEEN_SIMPLE):
        m = rx.search(q)
        if m:
            return _parse_hour_match(m, q, tz, now_local)
    return None


def _try_today(q: str, tz: ZoneInfo, now_local: datetime) -> ParsedAskTime | None:
    m = _RE_TODAY_WORD.search(q)
    if not m:
        return None
    if _RE_MORN_NOON.search(q):
        return None
    d = now_local.date()
    start = _local_midnight(d, tz).astimezone(timezone.utc)
    end = _utc_now().replace(microsecond=0)
    w = TimeWindow(start, end, end_exclusive=False)
    return ParsedAskTime(w, _strip_match(q, m))


def parse_ask_time_range(
    question: str,
    tz_name: str,
    now_utc: datetime | None = None,
) -> ParsedAskTime | None:
    """
    Detect a relative calendar/time window in the question (Arabic-first).
    Returns None if no time phrase matched.
    """
    raw = (question or "").strip()
    if not raw:
        return None
    q = _norm(raw)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
    now = now_utc or _utc_now()
    now_local = now.astimezone(tz)

    for fn in (
        _try_yesterday,
        _try_morning_noon,
        _try_between_hours,
        _try_today,
    ):
        got = fn(q, tz, now_local)
        if got:
            sq = re.sub(r"\s+", " ", got.search_query).strip()
            if not sq:
                sq = "أخبار أحداث"
            return ParsedAskTime(got.window, sq)
    return None
