from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from azure.identity.aio import DefaultAzureCredential
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.http.foundry_client import clear_foundry_client
from azure_integration.foundry.clients.webhook_client import FoundryWebhookClient

if TYPE_CHECKING:
    from azure_integration.foundry.clients.foundry_arm_client import FoundryArmClient

_ARM_SCOPE = "https://management.azure.com/.default"
_FOUNDRY_SCOPE = "https://ai.azure.com/.default"

_credential: DefaultAzureCredential | None = None
_arm_client: FoundryArmClient | None = None


class _FoundryHeaderProvider:
    """Bearer tokens for Foundry account-level webhook APIs."""

    def __init__(self) -> None:
        self._credential: DefaultAzureCredential | None = None

    async def get_authorization_header(self) -> dict[str, str]:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}


def azure_credential() -> DefaultAzureCredential:
    """Shared DAC for ARM management calls."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


async def management_headers() -> dict[str, str]:
    token = await azure_credential().get_token(_ARM_SCOPE)
    return {"Authorization": f"Bearer {token.token}"}


def create_foundry_arm_client() -> FoundryArmClient:
    global _arm_client
    if _arm_client is None:
        # Lazy import: FoundryArmClient imports management_headers at module load.
        from azure_integration.foundry.clients.foundry_arm_client import (
            FoundryArmClient,
        )

        _arm_client = FoundryArmClient()
    return _arm_client


def create_webhook_client_for_account(account_base_url: str) -> FoundryWebhookClient:
    return FoundryWebhookClient(
        http=OceanAsyncClient(timeout=httpx.Timeout(60.0)),
        authenticator=_FoundryHeaderProvider(),
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
