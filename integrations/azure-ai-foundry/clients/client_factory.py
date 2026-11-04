from __future__ import annotations

from typing import Any

from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.agent_observability_client import AgentObservabilityClient
from clients.arm_deployments_client import ArmDeploymentsClient
from clients.project_connections_client import ProjectConnectionsClient
from clients.auth.factory import create_authenticator
from clients.webhook_client import FoundryWebhookClient
from clients.http.foundry_client import FoundryHttpClient

_client: FoundryHttpClient | None = None
_arm_client: ArmDeploymentsClient | None = None
_connections_client: ProjectConnectionsClient | None = None
_observability_client: AgentObservabilityClient | None = None
_webhook_client: FoundryWebhookClient | None = None


def _create_authenticator(config: dict[str, Any]):
    return create_authenticator(config)


def create_foundry_client() -> FoundryHttpClient:
    global _client
    if _client is not None:
        return _client

    config: dict[str, Any] = ocean.integration_config
    api_version = str(
        config.get("api_version") or config.get("apiVersion") or "v1"
    )
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


def create_agent_observability_client() -> AgentObservabilityClient:
    global _observability_client
    if _observability_client is not None:
        return _observability_client
    _observability_client = AgentObservabilityClient(
        authenticator=_create_authenticator(ocean.integration_config)
    )
    return _observability_client


def _config_bool(config: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = config.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes"}
    return False


def create_webhook_client() -> FoundryWebhookClient:
    global _webhook_client
    if _webhook_client is not None:
        return _webhook_client
    config = ocean.integration_config
    secret = config.get("webhook_signing_secret") or config.get("webhookSigningSecret")
    verify = _config_bool(
        config, "verify_webhook_secrets", "verifyWebhookSecrets"
    )
    _webhook_client = FoundryWebhookClient(
        http=OceanAsyncClient(),
        signing_secret=str(secret) if secret else None,
        verify_secrets=verify,
        authenticator=_create_authenticator(config),
    )
    return _webhook_client


def clear_client_cache() -> None:
    global _client, _arm_client, _connections_client, _observability_client, _webhook_client
    from helpers.arm_scope import clear_arm_scope_cache

    _client = None
    _arm_client = None
    _connections_client = None
    _observability_client = None
    _webhook_client = None
    clear_arm_scope_cache()
