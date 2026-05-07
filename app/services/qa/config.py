"""LLM provider env parsing, TLS verify helper, and provider selection."""

import os
from typing import Any

import certifi

from app.shared.logger import build_logger

log = build_logger("ASK")

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "50000"))


def http_verify_setting():
    verify_raw = (os.getenv("SSL_VERIFY") or "true").strip().lower()
    if verify_raw in {"0", "false", "no", "off"}:
        log("ssl_verify", "info", "disabled by SSL_VERIFY=false")
        return False
    custom_bundle = (os.getenv("SSL_CA_BUNDLE") or "").strip()
    if custom_bundle:
        log("ssl_verify", "info", f"using custom CA bundle: {custom_bundle}")
        return custom_bundle
    return certifi.where()


def openai_config() -> tuple[str, dict[str, Any]] | None:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = (os.getenv("LLM_MODEL") or "gpt-4o-mini").strip()
    return "openai", {"key": key, "base": base, "model": model}


def ollama_config() -> tuple[str, dict[str, Any]] | None:
    model = (os.getenv("OLLAMA_MODEL") or "").strip()
    if not model:
        return None
    base = (os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
    return "ollama", {"base": base, "model": model}


def gemini_config() -> tuple[str, dict[str, Any]] | None:
    key = (
        (os.getenv("GEMINI_API_KEY") or "").strip()
        or (os.getenv("GOOGLE_API_KEY") or "").strip()
    )
    if not key:
        return None
    model = (os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip()
    return "gemini", {"key": key, "model": model}


def pick_provider() -> tuple[str | None, dict[str, Any] | None]:
    force = (os.getenv("LLM_PROVIDER") or "").lower().strip()
    if force == "gemini":
        g = gemini_config()
        if g:
            return g[0], g[1]
    if force == "ollama":
        o = ollama_config()
        if o:
            return o[0], o[1]
    if force == "openai":
        c = openai_config()
        if c:
            return c[0], c[1]
    c = openai_config()
    if c:
        return c[0], c[1]
    g = gemini_config()
    if g:
        return g[0], g[1]
    o = ollama_config()
    if o:
        return o[0], o[1]
    return None, None
