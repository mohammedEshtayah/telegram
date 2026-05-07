"""Q&A over stored news: provider wiring and public API."""

from app.utils.telegram_text import split_telegram

from .answer import answer_from_stored_news

__all__ = ["answer_from_stored_news", "split_telegram"]
