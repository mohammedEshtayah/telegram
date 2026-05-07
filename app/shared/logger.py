"""Small scoped logger factory."""


def build_logger(scope: str):
    def _log(step: str, status: str, details: str = "") -> None:
        if status == "ok":
            prefix = "OK"
        elif status == "fail":
            prefix = "ERR"
        else:
            prefix = "INFO"
        msg = f"[{prefix}] [{scope}] {step}"
        if details:
            msg += f" | {details}"
        print(msg)

    return _log
