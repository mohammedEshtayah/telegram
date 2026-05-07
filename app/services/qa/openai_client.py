"""OpenAI-compatible chat completions."""

import httpx

from .config import http_verify_setting, log


async def complete(messages: list[dict], cfg: dict) -> str:
    url = f"{cfg['base']}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['key']}"}
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0.3,
    }
    log("openai_request", "info", f"model={cfg['model']}")
    try:
        async with httpx.AsyncClient(
            timeout=120.0,
            verify=http_verify_setting(),
            trust_env=False,
        ) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response else None
        body = (e.response.text or "")[:300] if e.response else ""
        if status == 503 and "Web Page Blocked" in body:
            raise RuntimeError(
                "OpenAI is blocked on this network (Web Page Blocked). "
                "Try another network or host (e.g. Oracle VM)."
            ) from e
        if status == 401:
            raise RuntimeError("Invalid or expired OpenAI API key (401).") from e
        if status == 429:
            raise RuntimeError("OpenAI rate limit or insufficient quota (429).") from e
        raise RuntimeError(f"OpenAI request failed with HTTP {status}.") from e
    except httpx.HTTPError as e:
        raise RuntimeError(f"Could not reach OpenAI: {e}") from e
    log("openai_request", "ok", "response received")
    return (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
