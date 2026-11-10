from __future__ import annotations

from typing import Any

import httpx
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.helpers.scope import ensure_arm_deployment_scope


class ArmDeploymentsClient:
    """Create/delete model deployments via Azure Resource Manager."""

    def __init__(self) -> None:
        self._http = OceanAsyncClient(timeout=httpx.Timeout(120.0))

    async def close(self) -> None:
        await self._http.aclose()

    async def _headers(self) -> dict[str, str]:
        from azure_integration.foundry.clients.client_factory import management_headers

        return await management_headers()

    async def delete_deployment(self, deployment_name: str) -> None:
        scope = await ensure_arm_deployment_scope()
        response = await self._http.delete(
            scope.deployment_url(deployment_name),
            headers=await self._headers(),
        )
        if response.status_code in {200, 202, 204, 404}:
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
        properties: dict[str, Any] = {
            "model": {
                "format": model_publisher or "OpenAI",
                "name": model_name,
            }
        }
        if model_version:
            properties["model"]["version"] = model_version

        response = await self._http.put(
            scope.deployment_url(deployment_name),
            headers={**(await self._headers()), "Content-Type": "application/json"},
            json={
                "sku": {"name": sku_name, "capacity": capacity},
                "properties": properties,
            },
        )
        response.raise_for_status()
        if not response.content:
            return {"name": deployment_name}
        payload = response.json()
        return payload if isinstance(payload, dict) else {"name": deployment_name}
