"""Console logging for the channel bot (emoji prefixes)."""


def log(step: str, status: str, details: str = "") -> None:
    if status == "ok":
        prefix = "✅"
    elif status == "fail":
        prefix = "❌"
    else:
        prefix = "ℹ️"
    msg = f"{prefix} [BOT] {step}"
    if details:
        msg += f" | {details}"
    print(msg)
