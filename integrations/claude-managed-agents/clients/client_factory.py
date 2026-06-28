from typing import Any

from port_ocean.context.ocean import ocean

from clients.anthropic_client import AnthropicClient

_anthropic_client: AnthropicClient | None = None


def create_anthropic_client() -> AnthropicClient:
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client

    integration_config: dict[str, Any] = ocean.integration_config
    _anthropic_client = AnthropicClient(
        api_host=integration_config["anthropic_api_host"],
        api_key=integration_config["anthropic_api_key"],
        webhook_signing_secret=integration_config.get("webhook_signing_secret"),
    )
    return _anthropic_client
