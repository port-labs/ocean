from typing import Any

from port_ocean.context.ocean import ocean

from clients.cursor_client import DEFAULT_PAGE_SIZE, CursorClient

_cursor_client: CursorClient | None = None


def create_cursor_client() -> CursorClient:
    global _cursor_client
    if _cursor_client is not None:
        return _cursor_client

    integration_config: dict[str, Any] = ocean.integration_config
    _cursor_client = CursorClient(
        api_host=integration_config["cursor_api_host"],
        api_key=integration_config["cursor_api_key"],
        page_size=int(integration_config.get("cursor_page_size") or DEFAULT_PAGE_SIZE),
    )
    return _cursor_client
