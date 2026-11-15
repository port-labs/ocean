from typing import Any


def drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Omit unset filters; list values are sent as repeated query keys by httpx."""
    if params is None:
        return None
    return {key: value for key, value in params.items() if value is not None}
