from __future__ import annotations

from typing import Any

import httpx
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.auth.abstract_authenticator import AbstractAzureAuthenticator
from azure_integration.foundry.helpers.arm_scope import ensure_arm_deployment_scope


class ProjectConnectionsClient:
    """Create/update Foundry project connections (ARM) for MCP bearer auth."""

    _MANAGEMENT_SCOPE = "https://management.azure.com/.default"

    def __init__(
        self,
        *,
        authenticator: AbstractAzureAuthenticator,
    ) -> None:
        self._authenticator = authenticator
        self._http = OceanAsyncClient(timeout=httpx.Timeout(60.0))

    async def close(self) -> None:
        await self._http.aclose()

    async def _management_headers(self) -> dict[str, str]:
        credential = getattr(self._authenticator, "_credential", None)
        if credential is None:
            return await self._authenticator.get_authorization_header()
        token = await credential.get_token(self._MANAGEMENT_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def upsert_bearer_connection(
        self,
        *,
        project_name: str,
        connection_name: str,
        target_url: str,
        bearer_token: str,
    ) -> None:
        scope = await ensure_arm_deployment_scope()
        url = scope.project_connection_url(project_name, connection_name)
        headers = {
            **await self._management_headers(),
            "Content-Type": "application/json",
        }
        properties = _custom_keys_properties(target_url, bearer_token)
        body = {"properties": properties}

        get_response = await self._http.get(url, headers=headers)
        if get_response.status_code == 404:
            put_response = await self._http.put(url, headers=headers, json=body)
            put_response.raise_for_status()
            return

        get_response.raise_for_status()
        patch_response = await self._http.patch(url, headers=headers, json=body)
        patch_response.raise_for_status()


def _custom_keys_properties(target_url: str, bearer_token: str) -> dict[str, Any]:
    value = bearer_token if bearer_token.startswith("Bearer ") else f"Bearer {bearer_token}"
    return {
        "authType": "CustomKeys",
        "category": "CustomKeys",
        "target": target_url.rstrip("/"),
        "credentials": {"keys": {"Authorization": value}},
    }
