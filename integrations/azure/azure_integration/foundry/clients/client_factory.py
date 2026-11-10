from __future__ import annotations

from azure.identity.aio import DefaultAzureCredential

from azure_integration.foundry.clients.arm_deployments_client import (
    ArmDeploymentsClient,
)
from azure_integration.foundry.clients.http.foundry_client import (
    clear_foundry_client,
    create_foundry_client,
)

_ARM_SCOPE = "https://management.azure.com/.default"

_credential: DefaultAzureCredential | None = None
_arm_client: ArmDeploymentsClient | None = None

__all__ = [
    "clear_client_cache",
    "create_arm_deployments_client",
    "create_foundry_client",
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


async def clear_client_cache() -> None:
    global _arm_client, _credential
    await clear_foundry_client()
    if _arm_client is not None:
        await _arm_client.close()
    if _credential is not None:
        await _credential.close()
    _arm_client = None
    _credential = None
