"""Google Gemini generateContent client with retries and model fallbacks."""

import asyncio
import os
from typing import List, Optional

import httpx

from .config import http_verify_setting, log


def _models_sequence(primary: str) -> List[str]:
    out = [primary]
    raw = (os.getenv("GEMINI_MODEL_FALLBACK") or "").strip()
    if raw:
        for m in raw.split(","):
            m = m.strip()
            if m and m not in out:
                out.append(m)
    else:
        if primary == "gemini-2.0-flash" and "gemini-1.5-flash" not in out:
            out.append("gemini-1.5-flash")
    return out


def _messages_to_parts(messages: list[dict]) -> tuple[str, str]:
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


def _parse_response(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise RuntimeError(f"Empty Gemini response (blocked: {block}).")
        raise RuntimeError("Empty Gemini response (no candidates).")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [p.get("text") or "" for p in parts if isinstance(p, dict)]
    return "".join(texts).strip()


def _retryable_status(code: int) -> bool:
    return code in (429, 502, 503, 504)


async def complete(messages: list[dict], cfg: dict) -> str:
    sys_txt, user_txt = _messages_to_parts(messages)
    payload: dict = {
        "contents": [{"role": "user", "parts": [{"text": user_txt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    if sys_txt:
        payload["systemInstruction"] = {"parts": [{"text": sys_txt}]}
    params = {"key": cfg["key"]}
    models = _models_sequence(cfg["model"])
    max_retries = max(1, int(os.getenv("GEMINI_RETRY_COUNT", "4")))
    base_sec = float(os.getenv("GEMINI_RETRY_BASE_SEC", "2"))

    last_body = ""
    last_status: Optional[int] = None
    try:
        async with httpx.AsyncClient(
            timeout=120.0,
            verify=http_verify_setting(),
            trust_env=False,
        ) as client:
            for model in models:
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/"
                    f"models/{model}:generateContent"
                )
                for attempt in range(max_retries):
                    log(
                        "gemini_request",
                        "info",
                        f"model={model} attempt={attempt + 1}/{max_retries}",
                    )
                    r = await client.post(url, json=payload, params=params)
                    if r.status_code == 200:
                        log("gemini_request", "ok", f"model={model}")
                        return _parse_response(r.json())

                    last_status = r.status_code
                    last_body = (r.text or "")[:400]

                    if _retryable_status(r.status_code) and attempt < max_retries - 1:
                        wait = min(base_sec * (2**attempt), 60.0)
                        log("gemini_retry", "info", f"status={r.status_code} sleep_s={wait:.1f}")
                        await asyncio.sleep(wait)
                        continue

                    if _retryable_status(r.status_code):
                        log(
                            "gemini_request",
                            "fail",
                            f"model={model} status={r.status_code} -> try next model",
                        )
                        break

                    if r.status_code == 400:
                        raise RuntimeError(
                            "Invalid Gemini request (400). Check GEMINI_MODEL and API key."
                        )
                    if r.status_code == 403:
                        raise RuntimeError(
                            "Gemini API key rejected (403). Enable Generative Language API."
                        )
                    raise RuntimeError(
                        f"Gemini request failed with HTTP {r.status_code}: {last_body}"
                    )

            if last_status in (429, 503):
                raise RuntimeError(
                    "Gemini is busy or temporarily limited (429/503). "
                    "Retry later, or set GEMINI_MODEL=gemini-1.5-flash "
                    "or GEMINI_MODEL_FALLBACK=gemini-1.5-flash,gemini-1.5-pro in .env"
                )
            raise RuntimeError(
                f"Gemini failed after retries (last HTTP {last_status}): {last_body}"
            )
    except httpx.HTTPError as e:
        raise RuntimeError(f"Could not reach Gemini: {e}") from e
