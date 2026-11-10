from __future__ import annotations

import httpx
from azure.identity.aio import DefaultAzureCredential
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.arm_deployments_client import (
    ArmDeploymentsClient,
)
from azure_integration.foundry.clients.http.foundry_client import (
    FoundryAuthenticator,
    clear_foundry_client,
    create_foundry_client,
)
from azure_integration.foundry.clients.webhook_client import (
    FoundryWebhookClient,
    clear_webhook_secret_cache,
)
from azure_integration.foundry.discovery import clear_foundry_project_cache
from azure_integration.foundry.helpers.scope import clear_arm_scope_cache

_ARM_SCOPE = "https://management.azure.com/.default"

_credential: DefaultAzureCredential | None = None
_arm_client: ArmDeploymentsClient | None = None

__all__ = [
    "clear_client_cache",
    "create_arm_deployments_client",
    "create_foundry_client",
    "create_webhook_client_for_account",
    "management_headers",
]


def azure_credential() -> DefaultAzureCredential:
    """Shared DAC for ARM management calls."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


async def management_headers() -> dict[str, str]:
    token = await azure_credential().get_token(_ARM_SCOPE)
    return {"Authorization": f"Bearer {token.token}"}


def create_arm_deployments_client() -> ArmDeploymentsClient:
    global _arm_client
    if _arm_client is None:
        _arm_client = ArmDeploymentsClient()
    return _arm_client


def create_webhook_client_for_account(account_base_url: str) -> FoundryWebhookClient:
    return FoundryWebhookClient(
        http=OceanAsyncClient(timeout=httpx.Timeout(60.0)),
        authenticator=FoundryAuthenticator(),
        account_base_url=account_base_url,
    )


async def clear_client_cache() -> None:
    global _arm_client, _credential
    await clear_foundry_client()
    if _arm_client is not None:
        await _arm_client.close()
    if _credential is not None:
        await _credential.close()
    _arm_client = None
    _credential = None
    clear_arm_scope_cache()
    clear_foundry_project_cache()
    clear_webhook_secret_cache()
