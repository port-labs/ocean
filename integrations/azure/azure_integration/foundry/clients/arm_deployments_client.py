from __future__ import annotations

from typing import Any

import httpx
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.clients.http.rate_limit import FoundryRateLimiter
from azure_integration.foundry.core.exporters.project_exporter import ProjectExporter
from azure_integration.foundry.helpers.utils import deep_merge
from azure_integration.foundry.kinds import DEFAULT_FOUNDRY_ARM_API_VERSION


def _deployment_url(
    *,
    subscription_id: str,
    resource_group_name: str,
    account_name: str,
    deployment_name: str,
    api_version: str = DEFAULT_FOUNDRY_ARM_API_VERSION,
) -> str:
    return (
        "https://management.azure.com/subscriptions/"
        f"{subscription_id}/resourceGroups/{resource_group_name}"
        "/providers/Microsoft.CognitiveServices/accounts/"
        f"{account_name}/deployments/{deployment_name}"
        f"?api-version={api_version}"
    )


class ArmDeploymentsClient:
    """Create/delete model deployments via Azure Resource Manager."""

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

    async def _headers(self) -> dict[str, str]:
        from azure_integration.foundry.clients.client_factory import management_headers

        return await management_headers()

    async def _url_for(self, project_endpoint: str, deployment_name: str) -> str:
        project = await ProjectExporter().find_by_endpoint(project_endpoint)
        return _deployment_url(
            subscription_id=project.subscription_id,
            resource_group_name=project.resource_group_name,
            account_name=project.account_name,
            deployment_name=deployment_name,
        )

    async def delete_deployment(
        self, project_endpoint: str, deployment_name: str
    ) -> None:
        response = await self._http.delete(
            await self._url_for(project_endpoint, deployment_name),
            headers=await self._headers(),
        )
        if response.status_code in {200, 202, 204, 404}:
            return
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

        ``config`` is deep-merged under the ARM body so callers can pass SKU
        capacity, tags, raiPolicyName, and other properties we do not model.
        First-class fields always win.
        """
        properties: dict[str, Any] = {
            "model": {
                "format": model_publisher or "OpenAI",
                "name": model_name,
            }
        }
        if model_version:
            properties["model"]["version"] = model_version

        body = deep_merge(
            {
                "sku": {"name": sku_name, "capacity": capacity},
                "properties": properties,
            },
            config or {},
        )
        # First-class winners after config merge
        body.setdefault("sku", {})
        if isinstance(body["sku"], dict):
            body["sku"]["name"] = sku_name
            body["sku"].setdefault("capacity", capacity)
        body.setdefault("properties", {})
        if isinstance(body["properties"], dict):
            model = body["properties"].setdefault("model", {})
            if isinstance(model, dict):
                model["format"] = model_publisher or model.get("format") or "OpenAI"
                model["name"] = model_name
                if model_version:
                    model["version"] = model_version

        response = await self._http.put(
            await self._url_for(project_endpoint, deployment_name),
            headers={**(await self._headers()), "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        if not response.content:
            return {"name": deployment_name}
        payload = response.json()
        return payload if isinstance(payload, dict) else {"name": deployment_name}
