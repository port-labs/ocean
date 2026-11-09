from __future__ import annotations

from typing import Any

from azure.identity.aio import DefaultAzureCredential
from port_ocean.context.ocean import ocean

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.discovery import clear_foundry_project_cache
from azure_integration.foundry.helpers.arm_scope import clear_arm_scope_cache

_FOUNDRY_SCOPE = "https://ai.azure.com/.default"
_ARM_SCOPE = "https://management.azure.com/.default"

_credential: DefaultAzureCredential | None = None
_client: FoundryHttpClient | None = None


def azure_credential() -> DefaultAzureCredential:
    """Shared DAC. `ocean.on_start` already exports SP env vars when configured."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


class FoundryAuthenticator:
    def __init__(self) -> None:
        self._credential = azure_credential()

    async def get_authorization_header(self) -> dict[str, str]:
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}


async def management_headers() -> dict[str, str]:
    token = await azure_credential().get_token(_ARM_SCOPE)
    return {"Authorization": f"Bearer {token.token}"}


def create_foundry_client() -> FoundryHttpClient:
    global _client
    if _client is not None:
        return _client
    config: dict[str, Any] = ocean.integration_config
    api_version = str(config.get("api_version") or config.get("apiVersion") or "v1")
    _client = FoundryHttpClient(
        authenticator=FoundryAuthenticator(), api_version=api_version
    )
    return _client


async def clear_client_cache() -> None:
    global _client, _credential
    if _client is not None:
        await _client.close()
    if _credential is not None:
        await _credential.close()
    _client = None
    _credential = None
    clear_arm_scope_cache()
    clear_foundry_project_cache()
