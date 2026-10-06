from typing import Any

from port_ocean.context.ocean import ocean

from clients.cursor_agents_client import CursorAgentsClient

_cursor_agents_client: CursorAgentsClient | None = None


def create_cursor_agents_client() -> CursorAgentsClient:
    global _cursor_agents_client
    if _cursor_agents_client is not None:
        return _cursor_agents_client

    integration_config: dict[str, Any] = ocean.integration_config
    _cursor_agents_client = CursorAgentsClient(
        api_host=integration_config["cursor_api_host"],
        api_key=integration_config["cursor_api_key"],
        console_host=integration_config["cursor_console_host"],
    )
    return _cursor_agents_client
