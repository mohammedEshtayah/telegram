"""إجابات مبنيّة على أخبار مُخزّنة: Gemini أو OpenAI-متوافق أو Ollama."""
import asyncio
import os
from typing import List, Optional

import httpx
import certifi

from storage import search_relevant

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "50000"))


def _log(step: str, status: str, details: str = "") -> None:
    if status == "ok":
        prefix = "✅"
    elif status == "fail":
        prefix = "❌"
    else:
        prefix = "ℹ️"
    msg = f"{prefix} [ASK] {step}"
    if details:
        msg += f" | {details}"
    print(msg)


def _http_verify_setting():
    # Default: verify TLS using certifi bundle.
    # Set SSL_VERIFY=false in .env only when a corporate proxy injects a custom cert.
    verify_raw = (os.getenv("SSL_VERIFY") or "true").strip().lower()
    if verify_raw in {"0", "false", "no", "off"}:
        _log("ssl_verify", "info", "disabled by SSL_VERIFY=false")
        return False
    custom_bundle = (os.getenv("SSL_CA_BUNDLE") or "").strip()
    if custom_bundle:
        _log("ssl_verify", "info", f"using custom CA bundle: {custom_bundle}")
        return custom_bundle
    return certifi.where()


def _openai_config():
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (os.getenv("LLM_MODEL") or "gpt-4o-mini").strip()
    return "openai", {"key": key, "base": base, "model": model}


def _ollama_config():
    model = (os.getenv("OLLAMA_MODEL") or "").strip()
    if not model:
        return None
    base = (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    return "ollama", {"base": base, "model": model}


def _gemini_config():
    key = (
        (os.getenv("GEMINI_API_KEY") or "").strip()
        or (os.getenv("GOOGLE_API_KEY") or "").strip()
    )
    if not key:
        return None
    model = (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip()
    return "gemini", {"key": key, "model": model}


def _gemini_models_sequence(primary: str) -> List[str]:
    out = [primary]
    raw = (os.getenv("GEMINI_MODEL_FALLBACK") or "").strip()
    if raw:
        for m in raw.split(","):
            m = m.strip()
            if m and m not in out:
                out.append(m)
    else:
        # عند ضغط الطلب على النموذج الافتراضي، جرّب بديلاً خفيفاً تلقائياً.
        if primary == "gemini-2.0-flash" and "gemini-1.5-flash" not in out:
            out.append("gemini-1.5-flash")
    return out


def _pick_provider():
    force = (os.getenv("LLM_PROVIDER") or "").lower().strip()
    if force == "gemini":
        g = _gemini_config()
        if g:
            return g[0], g[1]
    if force == "ollama":
        o = _ollama_config()
        if o:
            return o[0], o[1]
    if force == "openai":
        c = _openai_config()
        if c:
            return c[0], c[1]
    c = _openai_config()
    if c:
        return c[0], c[1]
    g = _gemini_config()
    if g:
        return g[0], g[1]
    o = _ollama_config()
    if o:
        return o[0], o[1]
    return None, None


def _format_context(chunks: List[dict]) -> str:
    parts: List[str] = []
    n = 0
    for ch in chunks:
        n += 1
        src = ch.get("source") or "غير معروف"
        body = (ch.get("text") or "").strip()
        parts.append(f"--- [خبر {n} | المصدر: {src}]\n{body}\n")
    return "\n".join(parts)[:MAX_CONTEXT_CHARS]


def _build_messages(context: str, question: str) -> list[dict]:
    sys = (
        "أنت مساعد يجيب اعتماداً حصرياً على «سياق الأخبار» أدناه (لا تستخدم معلومات خارجها).\n"
        "• إذا وجدت في السياق ما يخص السؤال مباشرة أو حتى جزئياً أو من زاوية قريبة، "
        "لخّص ذلك بوضوح وربط الجمل بلائحة أو فقرات؛ لا ترفض الإجابة إذا كان هناك أي صلة موضوعية.\n"
        "• يمكنك دمج معلومات من أكثر من خبر إذا أكملت بعضها بعضاً.\n"
        "• قل إن المخزن لا يحتوي ما يكفي عن الموضوع فقط إذا لم يكن في السياق أي ذكر يتعلق بالسؤال "
        "ولا ما يمكن الاستناد إليه عن بعد.\n"
        "• لا تخترع أحداثاً أو أرقاماً غير واردة في السياق.\n"
        "• أجب بالعربية الفصحى المبسّطة، وبعناوين قصيرة إذا طال الجواب."
    )
    return [
        {"role": "system", "content": sys},
        {
            "role": "user",
            "content": f"سياق الأخبار:\n{context}\n\nالسؤال: {question}",
        },
    ]


async def _openai_complete(messages: list[dict], cfg: dict) -> str:
    url = f"{cfg['base']}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['key']}"}
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0.3,
    }
    _log("openai_request", "info", f"model={cfg['model']}")
    try:
        async with httpx.AsyncClient(
            timeout=120.0,
            verify=_http_verify_setting(),
            trust_env=False,
        ) as c:
            r = await c.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response else None
        body = (e.response.text or "")[:300] if e.response else ""
        if status == 503 and "Web Page Blocked" in body:
            raise RuntimeError(
                "الاتصال بـ OpenAI محجوب من الشبكة الحالية (Web Page Blocked). "
                "جرّب تشغيل البوت من Oracle VM أو شبكة مختلفة."
            ) from e
        if status == 401:
            raise RuntimeError("مفتاح OpenAI غير صحيح أو منتهي (401).") from e
        if status == 429:
            raise RuntimeError("تم تجاوز حدود OpenAI أو الرصيد غير كافٍ (429).") from e
        raise RuntimeError(f"فشل طلب OpenAI برمز HTTP {status}.") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"تعذر الاتصال بـ OpenAI: {e}") from e
    _log("openai_request", "ok", "response received")
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""


def _messages_to_gemini_parts(messages: list[dict]) -> tuple[str, str]:
    system_text = ""
    user_text = ""
    for m in messages:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role == "system":
            system_text = content
        elif role == "user":
            user_text = content
    return system_text, user_text


def _gemini_parse_response(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise RuntimeError(f"رد Gemini فارغ (محظور: {block}).")
        raise RuntimeError("رد Gemini بدون candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [p.get("text") or "" for p in parts if isinstance(p, dict)]
    return "".join(texts).strip()


def _gemini_retryable_status(code: int) -> bool:
    return code in (429, 502, 503, 504)


async def _gemini_complete(messages: list[dict], cfg: dict) -> str:
    sys_txt, user_txt = _messages_to_gemini_parts(messages)
    payload: dict = {
        "contents": [{"role": "user", "parts": [{"text": user_txt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    if sys_txt:
        payload["systemInstruction"] = {"parts": [{"text": sys_txt}]}
    params = {"key": cfg["key"]}
    models = _gemini_models_sequence(cfg["model"])
    max_retries = max(1, int(os.getenv("GEMINI_RETRY_COUNT", "4")))
    base_sec = float(os.getenv("GEMINI_RETRY_BASE_SEC", "2"))

    last_body = ""
    last_status: Optional[int] = None
    try:
        async with httpx.AsyncClient(
            timeout=120.0,
            verify=_http_verify_setting(),
            trust_env=False,
        ) as c:
            for model in models:
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/"
                    f"models/{model}:generateContent"
                )
                for attempt in range(max_retries):
                    _log(
                        "gemini_request",
                        "info",
                        f"model={model} attempt={attempt + 1}/{max_retries}",
                    )
                    r = await c.post(url, json=payload, params=params)
                    if r.status_code == 200:
                        _log("gemini_request", "ok", f"model={model}")
                        return _gemini_parse_response(r.json())

                    last_status = r.status_code
                    last_body = (r.text or "")[:400]

                    if _gemini_retryable_status(r.status_code) and attempt < max_retries - 1:
                        wait = min(base_sec * (2**attempt), 60.0)
                        _log(
                            "gemini_retry",
                            "info",
                            f"status={r.status_code} sleep_s={wait:.1f}",
                        )
                        await asyncio.sleep(wait)
                        continue

                    if _gemini_retryable_status(r.status_code):
                        _log(
                            "gemini_request",
                            "fail",
                            f"model={model} status={r.status_code} → try next model",
                        )
                        break

                    if r.status_code == 400:
                        raise RuntimeError(
                            "طلب Gemini غير صالح (400). تحقق من GEMINI_MODEL وصحة المفتاح."
                        )
                    if r.status_code == 403:
                        raise RuntimeError(
                            "تم رفض مفتاح Gemini (403). فعّل Generative Language API للمشروع."
                        )
                    raise RuntimeError(
                        f"فشل طلب Gemini برمز HTTP {r.status_code}: {last_body}"
                    )

            if last_status in (429, 503):
                raise RuntimeError(
                    "خدمة Gemini مشغولة أو محدودة مؤقتاً (429/503). "
                    "جرّب بعد دقائق، أو عيّن GEMINI_MODEL=gemini-1.5-flash "
                    "أو GEMINI_MODEL_FALLBACK=gemini-1.5-flash,gemini-1.5-pro في .env"
                )
            raise RuntimeError(
                f"فشل طلب Gemini بعد المحاولات (آخر رمز {last_status}): {last_body}"
            )
    except httpx.HTTPError as e:
        raise RuntimeError(f"تعذّر الاتصال بـ Gemini: {e}") from e


async def _ollama_complete(messages: list[dict], cfg: dict) -> str:
    url = f"{cfg['base']}/api/chat"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": False,
    }
    _log("ollama_request", "info", f"model={cfg['model']}")
    async with httpx.AsyncClient(timeout=180.0, verify=_http_verify_setting()) as c:
        r = await c.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    _log("ollama_request", "ok", "response received")
    msg = data.get("message") or {}
    return (msg.get("content") or "").strip()


async def answer_from_stored_news(question: str) -> str:
    _log("start", "info")
    q = (question or "").strip()
    if not q:
        _log("validate_question", "fail", "empty question")
        return "اكتب السؤال بعد الأمر: /ask ثم سؤالك"
    _log("validate_question", "ok", f"len={len(q)}")

    prov, cfg = _pick_provider()
    if not prov or not cfg:
        _log("provider_config", "fail", "missing provider settings in .env")
        return (
            "لم تُضبط خدمة اللغة. أضف في .env "
            "إمّا GEMINI_API_KEY (+ GEMINI_MODEL اختياري) "
            "أو OPENAI_API_KEY (+ LLM_MODEL اختياري) "
            "أو OLLAMA_MODEL مع تشغيل Ollama. "
            "أو اضبط LLM_PROVIDER=gemini|openai|ollama."
        )
    _log("provider_config", "ok", f"provider={prov}")

    rows = search_relevant(q, limit=45)
    if not rows:
        _log("search_relevant", "fail", "no rows in DB")
        return (
            "ما في أخبار مخزّنة حتى الآن. انتظر اكتمال تجميع الرسائل من القنوات، "
            "ثم جرّب /ask مرة أخرى."
        )
    _log("search_relevant", "ok", f"rows={len(rows)}")

    ctx = _format_context(rows)
    if not ctx.strip():
        _log("build_context", "fail", "empty context after formatting")
        return "تعذّر بناء سياق من المخزن. جرّب صيغة سؤال أبسط."
    _log("build_context", "ok", f"context_chars={len(ctx)}")

    messages = _build_messages(ctx, q)
    _log("build_messages", "ok", f"messages={len(messages)}")
    try:
        if prov == "gemini":
            ans = await _gemini_complete(messages, cfg)
        elif prov == "ollama":
            ans = await _ollama_complete(messages, cfg)
        else:
            ans = await _openai_complete(messages, cfg)
        _log("generate_answer", "ok", f"answer_chars={len(ans.strip())}")
        return ans
    except Exception as e:
        _log("generate_answer", "fail", str(e))
        raise


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
