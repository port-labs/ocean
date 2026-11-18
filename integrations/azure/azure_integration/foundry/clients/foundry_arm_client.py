from __future__ import annotations

from typing import Any

import httpx
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.client_factory import management_headers
from azure_integration.foundry.clients.http.rate_limit import FoundryRateLimiter
from azure_integration.foundry.core.exporters.project_exporter import (
    FoundryProject,
    ProjectExporter,
    foundry_project_from_arm_id,
)
from azure_integration.foundry.kinds import DEFAULT_FOUNDRY_ARM_API_VERSION


class FoundryArmClient:
    """Azure Resource Manager calls for Foundry (deployments, project connections)."""

    def __init__(self) -> None:
        self.rate_limiter = FoundryRateLimiter()
        self._http = OceanAsyncClient(
            timeout=httpx.Timeout(120.0),
            event_hooks={"response": [self._on_response]},
        )

    async def _on_response(self, response: httpx.Response) -> None:
        self.rate_limiter.observe(response)

    async def close(self) -> None:
        await self._http.aclose()

    async def _project(
        self,
        project_endpoint: str,
        *,
        project_arm_id: str | None = None,
    ) -> FoundryProject:
        if project_arm_id:
            project = foundry_project_from_arm_id(project_arm_id)
            if project is None:
                raise ValueError(f"Invalid Foundry project ARM id: {project_arm_id}")
            return project
        return await ProjectExporter().find_by_endpoint(project_endpoint)

    async def _url_for(
        self,
        project_endpoint: str,
        deployment_name: str,
        *,
        project_arm_id: str | None = None,
    ) -> str:
        project = await self._project(
            project_endpoint, project_arm_id=project_arm_id
        )
        return (
            "https://management.azure.com/subscriptions/"
            f"{project.subscription_id}/resourceGroups/{project.resource_group_name}"
            "/providers/Microsoft.CognitiveServices/accounts/"
            f"{project.account_name}/deployments/{deployment_name}"
            f"?api-version={DEFAULT_FOUNDRY_ARM_API_VERSION}"
        )

    async def upsert_project_connection(
        self,
        *,
        project_endpoint: str,
        name: str,
        target: str,
        access_token: str,
        project_arm_id: str | None = None,
    ) -> None:
        """Create/update a RemoteTool CustomKeys connection (MCP auth).

        Data-plane ``/connections`` is read-only; create/update is ARM only.
        """
        project = await self._project(
            project_endpoint, project_arm_id=project_arm_id
        )
        token = access_token.strip()
        if not token.lower().startswith("bearer "):
            token = f"Bearer {token}"
        url = (
            "https://management.azure.com/subscriptions/"
            f"{project.subscription_id}/resourceGroups/{project.resource_group_name}"
            "/providers/Microsoft.CognitiveServices/accounts/"
            f"{project.account_name}/projects/{project.project_name}"
            f"/connections/{name}"
            f"?api-version={DEFAULT_FOUNDRY_ARM_API_VERSION}"
        )
        response = await self._http.put(
            url,
            headers={
                **(await management_headers()),
                "Content-Type": "application/json",
            },
            json={
                "properties": {
                    "authType": "CustomKeys",
                    "category": "RemoteTool",
                    "target": target,
                    "credentials": {"keys": {"Authorization": token}},
                    "metadata": {"type": "generic_mcp"},
                }
            },
        )
        response.raise_for_status()

    async def delete_deployment(
        self, project_endpoint: str, deployment_name: str
    ) -> None:
        response = await self._http.delete(
            await self._url_for(project_endpoint, deployment_name),
            headers=await management_headers(),
        )
        if response.status_code != 404:
            response.raise_for_status()

    async def upsert_model_deployment(
        self,
        *,
        project_endpoint: str,
        deployment_name: str,
        model_name: str,
        model_version: str | None,
        model_publisher: str | None,
        sku_name: str,
        capacity: int = 1,
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """PUT a Cognitive Services account deployment.

        ``config`` may pass through ARM extras (capacity, tags, raiPolicyName).
        First-class ``sku_name`` / model fields always win and are not taken from
        ``config``.
        """
        model: dict[str, Any] = {
            "format": model_publisher or "OpenAI",
            "name": model_name,
        }
        if model_version:
            model["version"] = model_version

        overlay = dict(config or {})
        sku_extra = dict(overlay.pop("sku", {}) or {})
        sku_extra.pop("name", None)
        props_extra = dict(overlay.pop("properties", {}) or {})
        props_extra.pop("model", None)

        body: dict[str, Any] = {
            **overlay,
            "sku": {"capacity": capacity, **sku_extra, "name": sku_name},
            "properties": {**props_extra, "model": model},
        }

        response = await self._http.put(
            await self._url_for(project_endpoint, deployment_name),
            headers={
                **(await management_headers()),
                "Content-Type": "application/json",
            },
            json=body,
        )
        response.raise_for_status()
        if not response.content:
            return {"name": deployment_name}
        payload = response.json()
        return payload if isinstance(payload, dict) else {"name": deployment_name}
