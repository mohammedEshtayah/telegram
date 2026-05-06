"""تخزين مفاتيح لأخبار منقولة لاستعمالها لاحقاً في أسئلة-أجوبة."""
import html
import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone

NEWS_DB_PATH = os.getenv("NEWS_DB_PATH", "news.db")
MAX_STORE_CHARS = 12000
_SCAN_LAST_ROWS = 8000


def _log(step: str, status: str, details: str = "") -> None:
    if status == "ok":
        prefix = "✅"
    elif status == "fail":
        prefix = "❌"
    else:
        prefix = "ℹ️"
    msg = f"{prefix} [DB] {step}"
    if details:
        msg += f" | {details}"
    print(msg)


@contextmanager
def _db():
    conn = sqlite3.connect(NEWS_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    _log("init_db", "info", f"path={NEWS_DB_PATH}")
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
    _log("init_db", "ok", "tables/index ready")


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
    _log("persist_from_caption", "info", f"source={source} stream={stream}")
    plain = html_to_plain(caption_html)
    if len(plain) < 5:
        _log("persist_from_caption", "fail", "caption too short")
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
    _log("persist_from_caption", "ok", f"saved_chars={len(plain)}")


_AR_WORD = re.compile(r"[\u0600-\u06FFa-zA-Z0-9_]+", re.UNICODE)


def normalize_for_match(s: str) -> str:
    """توحيد أشكال الحروف العربية الشائعة لتحسين التطابق بين السؤال والمخزن."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.translate(str.maketrans({"\u0649": "\u064a", "\u0629": "\u0647"}))
    for ch in ("\u0622", "\u0623", "\u0625", "\u0671"):
        s = s.replace(ch, "\u0627")
    s = s.replace("\u0640", "")
    return s.casefold()


_STOP = frozenset(
    normalize_for_match(w)
    for w in """
    و من الى في على عن أن ما مع إلى ان لا الذى التي الذين هل لك كم هو هي هم
    هذ هذه ذلك تلك انا انت انتم انتم يا ؟
    give me a an the is are was were of for to and or not
    """.split()
    if w.strip()
)


def _query_terms(q: str) -> list[str]:
    qn = normalize_for_match(q)
    words = [w for w in _AR_WORD.findall(qn) if len(w) > 1 and w not in _STOP]
    if not words:
        words = [w for w in _AR_WORD.findall(qn) if len(w) > 0]
    return list(dict.fromkeys(words))  # order-preserving unique


def search_relevant(query: str, limit: int = 40) -> list[dict]:
    _log("search_relevant", "info", f"limit={limit}")
    terms = _query_terms(query)
    _log("search_relevant", "info", f"terms={len(terms)}")
    with _db() as conn:
        cur = conn.execute(
            "SELECT id, text, source, stream, created_at FROM news ORDER BY id DESC LIMIT ?",
            (_SCAN_LAST_ROWS,),
        )
        rows = cur.fetchall()
    _log("search_relevant", "ok", f"rows_scanned={len(rows)}")

    q_sub = normalize_for_match(query.strip())[:500]

    def score_text(text: str) -> float:
        t = normalize_for_match(text)
        if not t:
            return 0.0
        s = 0.0
        for term in terms:
            c = t.count(term)
            s += 1.0 + min(5.0, c) * 0.15
        if q_sub and q_sub in t:
            s += 2.5
        if not terms and query.strip():
            raw_snip = normalize_for_match(query.strip()[:200])
            if raw_snip and raw_snip in t:
                s = max(s, 0.35)
        return s

    scored: list[tuple[float, sqlite3.Row]] = []
    for r in rows:
        sc = score_text(r["text"])
        if sc > 0:
            scored.append((sc, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored and rows:
        # فallback: آخر N عناصر إن لم يلتقط أي تطابق بسيط
        pool = list(rows)[: min(limit, len(rows))]
    else:
        # دمج: أعلى تطابق + أحدث العناصر (حتى لا يختصر السياق على كلمات ضعيفة فقط)
        head_n = max(1, limit - min(18, limit))
        pool_rows = [r[1] for r in scored[:head_n]]
        seen = {r["id"] for r in pool_rows}
        for r in rows:
            if len(pool_rows) >= limit:
                break
            if r["id"] not in seen:
                seen.add(r["id"])
                pool_rows.append(r)
        pool = pool_rows

    out: list[dict] = []
    for r in pool:
        if len(r["text"] or "") < 8:
            continue
        out.append(
            {
                "id": r["id"],
                "text": (r["text"] or "")[:10000],
                "source": r["source"] or "",
                "stream": r["stream"] or "",
                "created_at": r["created_at"] or "",
            }
        )
        if len(out) >= limit:
            break

    if not out and rows:
        for r in rows[:limit]:
            out.append(
                {
                    "id": r["id"],
                    "text": (r["text"] or "")[:10000],
                    "source": r["source"] or "",
                    "stream": r["stream"] or "",
                    "created_at": r["created_at"] or "",
                }
            )
    _log("search_relevant", "ok", f"rows_returned={len(out)}")
    return out
