from typing import Any

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200


def drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Omit unset filters; list values are sent as repeated query keys by httpx."""
    if params is None:
        return None
    return {key: value for key, value in params.items() if value is not None}


def build_list_page_params(
    params: dict[str, Any] | None,
    *,
    after: str | None,
    page_size: int,
    max_page_size: int = MAX_PAGE_SIZE,
) -> dict[str, Any]:
    page_params = dict(params or {})
    page_params["first"] = min(page_size, max_page_size)
    if after:
        page_params["after"] = after
    return page_params
