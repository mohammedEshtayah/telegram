"""Store and query forwarded news for later Q&A usage."""
import base64
import html
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from app.config.settings import NEWS_DB_PATH
from app.shared.logger import build_logger
from app.utils.telegram_text import strip_known_noise

log = build_logger("DB")
MAX_STORE_CHARS = 12000
_SCAN_LAST_ROWS = 8000


@contextmanager
def _db():
    conn = sqlite3.connect(NEWS_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    log("init_db", "info", f"path={NEWS_DB_PATH}")
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                source TEXT,
                stream TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_id ON news(id);")
        conn.commit()
    log("init_db", "ok", "tables/index ready")


def html_to_plain(s: str) -> str:
    s = s or ""
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</p\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\u200c]+", " ", s)
    s = re.sub(r"\n+", "\n", s)
    return s.strip()


def persist_from_caption(caption_html: str, source: str, stream: str) -> None:
    log("persist_from_caption", "info", f"source={source} stream={stream}")
    plain = strip_known_noise(html_to_plain(caption_html))
    if len(plain) < 5:
        log("persist_from_caption", "fail", "caption too short")
        return
    if len(plain) > MAX_STORE_CHARS:
        plain = plain[:MAX_STORE_CHARS]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    with _db() as conn:
        conn.execute(
            "INSERT INTO news (text, source, stream, created_at) VALUES (?, ?, ?, ?)",
            (plain, (source or "")[:500], (stream or "")[:64], now),
        )
        conn.commit()
    log("persist_from_caption", "ok", f"saved_chars={len(plain)}")


_AR_WORD = re.compile(r"[\u0600-\u06FFa-zA-Z0-9_]+", re.UNICODE)


def normalize_for_match(s: str) -> str:
    """Normalize Arabic variants to improve query matching."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.translate(str.maketrans({"\u0649": "\u064a", "\u0629": "\u0647"}))
    for ch in ("\u0622", "\u0623", "\u0625", "\u0671"):
        s = s.replace(ch, "\u0627")
    s = s.replace("\u0640", "")
    return s.casefold()


# Arabic + English stopwords for matching (stored as base64 to keep source ASCII-only).
_STOP_BYTES = base64.b64decode(
    "CiAgICDZiCDZhdmGINin2YTZiSDZgdmKINi52YTZiSDYudmGINij2YYg2YXYpyDZhdi5INil2YTZiSDYp9mGINmE2Kcg2KfZhNiw2Ykg2KfZhNiq2Yog2KfZhNiw2YrZhiDZh9mEINmE2YMg2YPZhSDZh9mIINmH2Yog2YfZhQogICAg2YfYsCDZh9iw2Ycg2LDZhNmDINiq2YTZgyDYp9mG2Kcg2KfZhtiqINin2YbYqtmFINin2YbYqtmFINmK2Kcg2J8KICAgIGdpdmUgbWUgYSBhbiB0aGUgaXMgYXJlIHdhcyB3ZXJlIG9mIGZvciB0byBhbmQgb3Igbm90CiAgICA="
)
_STOP = frozenset(
    normalize_for_match(w)
    for w in _STOP_BYTES.decode("utf-8").split()
    if w.strip()
)


def _query_terms(q: str) -> list[str]:
    qn = normalize_for_match(q)
    words = [w for w in _AR_WORD.findall(qn) if len(w) > 1 and w not in _STOP]
    if not words:
        words = [w for w in _AR_WORD.findall(qn) if len(w) > 0]
    return list(dict.fromkeys(words))


def search_relevant(
    query: str,
    limit: int = 40,
    *,
    window_start_utc: Optional[datetime] = None,
    window_end_utc: Optional[datetime] = None,
    window_end_exclusive: bool = True,
) -> list[dict]:
    log("search_relevant", "info", f"limit={limit}")
    terms = _query_terms(query)
    log("search_relevant", "info", f"terms={len(terms)}")
    conds: list[str] = []
    params: list = []
    if window_start_utc is not None:
        ws = window_start_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        conds.append("created_at >= ?")
        params.append(ws)
    if window_end_utc is not None:
        we = window_end_utc.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        conds.append("created_at < ?" if window_end_exclusive else "created_at <= ?")
        params.append(we)
    where = (" WHERE " + " AND ".join(conds)) if conds else ""
    params.append(_SCAN_LAST_ROWS)
    sql = (
        "SELECT id, text, source, stream, created_at FROM news"
        f"{where} ORDER BY id DESC LIMIT ?"
    )
    with _db() as conn:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    log("search_relevant", "ok", f"rows_scanned={len(rows)}")

    q_sub = normalize_for_match(query.strip())[:500]

    def score_text(text: str) -> float:
        t = normalize_for_match(text)
        if not t:
            return 0.0
        score = 0.0
        for term in terms:
            count = t.count(term)
            score += 1.0 + min(5.0, count) * 0.15
        if q_sub and q_sub in t:
            score += 2.5
        if not terms and query.strip():
            raw_snip = normalize_for_match(query.strip()[:200])
            if raw_snip and raw_snip in t:
                score = max(score, 0.35)
        return score

    scored: list[tuple[float, sqlite3.Row]] = []
    for row in rows:
        sc = score_text(row["text"])
        if sc > 0:
            scored.append((sc, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored and rows:
        pool = list(rows)[: min(limit, len(rows))]
    else:
        head_n = max(1, limit - min(18, limit))
        pool_rows = [r[1] for r in scored[:head_n]]
        seen = {r["id"] for r in pool_rows}
        for row in rows:
            if len(pool_rows) >= limit:
                break
            if row["id"] not in seen:
                seen.add(row["id"])
                pool_rows.append(row)
        pool = pool_rows

    out: list[dict] = []
    for row in pool:
        if len(row["text"] or "") < 8:
            continue
        out.append(
            {
                "id": row["id"],
                "text": (row["text"] or "")[:10000],
                "source": row["source"] or "",
                "stream": row["stream"] or "",
                "created_at": row["created_at"] or "",
            }
        )
        if len(out) >= limit:
            break

    if not out and rows:
        for row in rows[:limit]:
            out.append(
                {
                    "id": row["id"],
                    "text": (row["text"] or "")[:10000],
                    "source": row["source"] or "",
                    "stream": row["stream"] or "",
                    "created_at": row["created_at"] or "",
                }
            )
    log("search_relevant", "ok", f"rows_returned={len(out)}")
    return out
