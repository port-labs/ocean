from __future__ import annotations

from typing import Any

import httpx
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.auth.abstract_authenticator import AbstractAzureAuthenticator
from helpers.arm_scope import ensure_arm_deployment_scope


class ArmDeploymentsClient:
    """Create/delete model deployments via Azure Resource Manager."""

    _MANAGEMENT_SCOPE = "https://management.azure.com/.default"

    def __init__(
        self,
        *,
        authenticator: AbstractAzureAuthenticator,
    ) -> None:
        self._authenticator = authenticator
        self._http = OceanAsyncClient(timeout=httpx.Timeout(120.0))

    async def close(self) -> None:
        await self._http.aclose()

    async def _management_headers(self) -> dict[str, str]:
        credential = getattr(self._authenticator, "_credential", None)
        if credential is None:
            return await self._authenticator.get_authorization_header()
        token = await credential.get_token(self._MANAGEMENT_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def delete_deployment(self, deployment_name: str) -> None:
        scope = await ensure_arm_deployment_scope()
        response = await self._http.delete(
            scope.deployment_url(deployment_name),
            headers=await self._management_headers(),
        )
        if response.status_code in {200, 202, 204}:
            return
        response.raise_for_status()

    async def upsert_model_deployment(
        self,
        *,
        deployment_name: str,
        model_name: str,
        model_version: str | None,
        model_publisher: str | None,
        sku_name: str,
        capacity: int = 1,
    ) -> dict[str, Any]:
        scope = await ensure_arm_deployment_scope()
        model_format = model_publisher or "OpenAI"
        properties: dict[str, Any] = {
            "model": {
                "format": model_format,
                "name": model_name,
            }
        }
        if model_version:
            properties["model"]["version"] = model_version

        body = {
            "sku": {"name": sku_name, "capacity": capacity},
            "properties": properties,
        }
        response = await self._http.put(
            scope.deployment_url(deployment_name),
            headers={
                **await self._management_headers(),
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        if not response.content:
            return {"name": deployment_name}
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        return {"name": deployment_name}
