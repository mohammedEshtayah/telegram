"""Stateful pipeline: register Telethon handlers for forward + /ask."""

from __future__ import annotations

import difflib
from typing import Any

from telethon import TelegramClient, events

from app.config.settings import (
    SOURCE_CHANNELS,
    TARGET_CHANNEL_MAIN,
    TARGET_CHANNEL_STREETS,
)

from . import ask_handler, forward_handlers


class ChannelForwardPipeline:
    """Register with ``register()`` on a Telethon client."""

    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self.target_channel = TARGET_CHANNEL_MAIN
        self.target_channel_streets = TARGET_CHANNEL_STREETS
        self.source_channels = SOURCE_CHANNELS

        self.dic_count_group: dict[str, int] = {}
        self.dic_message: dict[str, str] = {}
        self.dic_group_dup_confirm: dict[str, bool] = {}
        self.recent_entries: list[dict[str, Any]] = []
        # Default: skip forwards when body matches a recent post on the same target.
        # /dup allows forwarding duplicates; /undeplh turns skipping back on.
        self.forward_duplicate_messages: bool = False

    def duplicate_match(
        self, text: str, target_chat_id: int, threshold: float = 0.8
    ) -> dict | None:
        for entry in reversed(self.recent_entries):
            if entry.get("target_chat_id") != target_chat_id:
                continue
            prev = entry.get("text") or ""
            if difflib.SequenceMatcher(None, text, prev).ratio() >= threshold:
                return entry
        return None

    def add_to_recent(
        self, text: str, target_chat_id: int, msg_id: int, limit: int = 500
    ) -> None:
        if not text or msg_id is None:
            return
        self.recent_entries.append(
            {"text": text, "target_chat_id": target_chat_id, "msg_id": int(msg_id)}
        )
        while len(self.recent_entries) > limit:
            self.recent_entries.pop(0)

    async def _on_ask(self, event) -> None:
        await ask_handler.handle_ask(self, event)

    async def _on_forward(self, event) -> None:
        await forward_handlers.handle_forward_dispatch(self, event)

    def register(self) -> None:
        self.client.add_event_handler(self._on_ask, events.NewMessage())
        self.client.add_event_handler(
            self._on_forward,
            events.NewMessage(chats=self.source_channels),
        )
