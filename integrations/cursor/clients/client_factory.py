from typing import Any

from port_ocean.context.ocean import ocean

from clients.cursor_client import CursorClient

_cursor_client: CursorClient | None = None


def create_cursor_client() -> CursorClient:
    global _cursor_client
    if _cursor_client is not None:
        return _cursor_client

    integration_config: dict[str, Any] = ocean.integration_config
    _cursor_client = CursorClient(
        api_host=integration_config["cursor_api_host"],
        api_key=integration_config["cursor_api_key"],
    )
    return _cursor_client
