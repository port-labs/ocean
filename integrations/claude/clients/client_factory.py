from typing import Any

from port_ocean.context.ocean import ocean

from clients.claude_client import ClaudeClient

_claude_client: ClaudeClient | None = None


def create_claude_client() -> ClaudeClient:
    global _claude_client
    if _claude_client is not None:
        return _claude_client

    integration_config: dict[str, Any] = ocean.integration_config
    _claude_client = ClaudeClient(
        api_host=integration_config["anthropic_api_host"],
        api_key=integration_config["anthropic_api_key"],
    )
    return _claude_client
