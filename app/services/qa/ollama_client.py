"""Ollama /api/chat client."""

import httpx

from .config import http_verify_setting, log


async def complete(messages: list[dict], cfg: dict) -> str:
    url = f"{cfg['base']}/api/chat"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": False,
    }
    log("ollama_request", "info", f"model={cfg['model']}")
    async with httpx.AsyncClient(timeout=180.0, verify=http_verify_setting()) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    log("ollama_request", "ok", "response received")
    msg = data.get("message") or {}
    return (msg.get("content") or "").strip()
