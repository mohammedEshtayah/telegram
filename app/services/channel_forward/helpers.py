"""Small Telethon send-result helpers."""


def first_sent_message_id(result) -> int | None:
    if result is None:
        return None
    if isinstance(result, list):
        return result[0].id if result else None
    return getattr(result, "id", None)


def group_source_text(media_group) -> str:
    for msg in media_group:
        if msg.text:
            return (msg.text or "").strip()
    return ""
