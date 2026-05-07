"""Facade for Q&A imports; implementation lives in ``app.services.qa``."""

from app.services.qa import answer_from_stored_news, split_telegram

__all__ = ["answer_from_stored_news", "split_telegram"]
