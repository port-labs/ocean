from __future__ import annotations

from azure.identity.aio import DefaultAzureCredential

from clients.auth.abstract_authenticator import AbstractAzureAuthenticator

_FOUNDRY_SCOPE = "https://ai.azure.com/.default"


class DefaultAzureCredentialAuthenticator(AbstractAzureAuthenticator):
    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()

    async def get_authorization_header(self) -> dict[str, str]:
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def close(self) -> None:
        await self._credential.close()
