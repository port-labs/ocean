from __future__ import annotations

from typing import Any

import httpx
from azure.identity.aio import ClientSecretCredential

from clients.auth.abstract_authenticator import AbstractAzureAuthenticator

_FOUNDRY_SCOPE = "https://ai.azure.com/.default"


class ServicePrincipalAuthenticator(AbstractAzureAuthenticator):
    def __init__(
        self, *, tenant_id: str, client_id: str, client_secret: str
    ) -> None:
        self._credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

    async def get_authorization_header(self) -> dict[str, str]:
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def close(self) -> None:
        await self._credential.close()

    @classmethod
    def from_integration_config(
        cls, config: dict[str, Any]
    ) -> ServicePrincipalAuthenticator | None:
        tenant_id = config.get("azure_tenant_id") or config.get("azureTenantId")
        client_id = config.get("azure_client_id") or config.get("azureClientId")
        client_secret = config.get("azure_client_secret") or config.get(
            "azureClientSecret"
        )
        if not tenant_id or not client_id or not client_secret:
            return None
        return cls(
            tenant_id=str(tenant_id),
            client_id=str(client_id),
            client_secret=str(client_secret),
        )
