from typing import Any

from port_ocean.context.ocean import ocean

from clients.anthropic_client import AnthropicClient
from clients.webhook_client import ClaudeWebhookClient

_anthropic_client: AnthropicClient | None = None
_webhook_client: ClaudeWebhookClient | None = None


def create_anthropic_client() -> AnthropicClient:
    global _anthropic_client
    if _anthropic_client is not None:
        return _anthropic_client

    integration_config: dict[str, Any] = ocean.integration_config
    _anthropic_client = AnthropicClient(
        api_host=integration_config["anthropic_api_host"],
        api_key=integration_config["anthropic_api_key"],
        console_host=integration_config["platform_console_host"],
        anthropic_version=integration_config.get("anthropic_version"),
    )
    return _anthropic_client


def create_webhook_client() -> ClaudeWebhookClient:
    global _webhook_client
    if _webhook_client is not None:
        return _webhook_client

    anthropic = create_anthropic_client()
    integration_config: dict[str, Any] = ocean.integration_config
    _webhook_client = ClaudeWebhookClient(
        http_client=anthropic.http_client,
        anthropic_client=anthropic.async_client,
        console_host=integration_config["platform_console_host"],
        api_key=anthropic.api_key,
        webhook_signing_secret=integration_config.get("webhook_signing_secret"),
        verify_webhook_secrets=bool(
            integration_config.get("verify_webhook_secrets", False)
        ),
        anthropic_version=anthropic.anthropic_version,
    )
    return _webhook_client
