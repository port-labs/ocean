from __future__ import annotations

from typing import Any

from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.arm_deployments_client import ArmDeploymentsClient
from azure_integration.foundry.clients.project_connections_client import (
    ProjectConnectionsClient,
)
from azure_integration.foundry.clients.auth.factory import create_authenticator
from azure_integration.foundry.clients.webhook_client import (
    FoundryWebhookClient,
    clear_webhook_secret_cache,
)
from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient

_client: FoundryHttpClient | None = None
_arm_client: ArmDeploymentsClient | None = None
_connections_client: ProjectConnectionsClient | None = None


def _create_authenticator(config: dict[str, Any]):
    return create_authenticator(config)


def create_foundry_client() -> FoundryHttpClient:
    global _client
    if _client is not None:
        return _client

    config: dict[str, Any] = ocean.integration_config
    api_version = str(config.get("api_version") or config.get("apiVersion") or "v1")
    _client = FoundryHttpClient(
        authenticator=_create_authenticator(config), api_version=api_version
    )
    return _client


def create_arm_deployments_client() -> ArmDeploymentsClient:
    global _arm_client
    if _arm_client is not None:
        return _arm_client
    _arm_client = ArmDeploymentsClient(
        authenticator=_create_authenticator(ocean.integration_config)
    )
    return _arm_client


def create_project_connections_client() -> ProjectConnectionsClient:
    global _connections_client
    if _connections_client is not None:
        return _connections_client
    _connections_client = ProjectConnectionsClient(
        authenticator=_create_authenticator(ocean.integration_config)
    )
    return _connections_client


def create_webhook_client_for_account(account_base_url: str) -> FoundryWebhookClient:
    return FoundryWebhookClient(
        http=OceanAsyncClient(),
        authenticator=_create_authenticator(ocean.integration_config),
        account_base_url=account_base_url,
        verify_secrets=True,
    )


def create_webhook_client() -> FoundryWebhookClient:
    """Legacy helper: webhook client for current project context account host."""
    from azure_integration.foundry.helpers.project_scope import get_project_endpoint
    from azure_integration.foundry.helpers.webhook_scope import (
        account_base_url_from_project_endpoint,
    )

    return create_webhook_client_for_account(
        account_base_url_from_project_endpoint(get_project_endpoint())
    )


def clear_client_cache() -> None:
    global _client, _arm_client, _connections_client
    from azure_integration.foundry.helpers.arm_scope import clear_arm_scope_cache
    from azure_integration.foundry.discovery import clear_foundry_project_cache

    _client = None
    _arm_client = None
    _connections_client = None
    clear_arm_scope_cache()
    clear_foundry_project_cache()
    clear_webhook_secret_cache()
