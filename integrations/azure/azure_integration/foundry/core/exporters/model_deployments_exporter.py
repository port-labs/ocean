from __future__ import annotations

from typing import Any

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListModelDeploymentsOptions
from azure_integration.foundry.foundry_incremental import MODEL_DEPLOYMENT_INCREMENTAL
from azure_integration.foundry.helpers.utils import enrich_with_project, timestamp_to_iso


class ModelDeploymentsExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: ListModelDeploymentsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options["project_endpoint"]
        project_id = options["project_id"]
        cursor = active_incremental_cursor()
        params = MODEL_DEPLOYMENT_INCREMENTAL.merge_params({}, cursor)

        async for page in paginate_with_strategy(
            self.client.send_paginated_request(
                project_endpoint, "deployments", params=params
            ),
            cursor=cursor,
            strategy=MODEL_DEPLOYMENT_INCREMENTAL,
        ):
            batch = [
                enrich_with_project(
                    _normalize_deployment(item),
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if batch:
                yield batch


def _normalize_deployment(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    deployment_id = item.get("id") or item.get("name")
    if deployment_id is not None:
        normalized["id"] = deployment_id
    model_name = item.get("model") or item.get("modelName")
    if model_name is not None:
        normalized["model"] = model_name
    sku = item.get("sku")
    if isinstance(sku, dict) and sku.get("name") is not None:
        normalized["sku"] = sku["name"]
    elif isinstance(sku, str):
        normalized["sku"] = sku
    deployment_type = item.get("type") or item.get("deploymentType")
    if deployment_type is not None:
        normalized["deployment_type"] = deployment_type
    if item.get("modelVersion") is not None:
        normalized["model_version"] = item["modelVersion"]
    if item.get("modelPublisher") is not None:
        normalized["model_publisher"] = item["modelPublisher"]
    capabilities = item.get("capabilities")
    if isinstance(capabilities, dict):
        normalized["capabilities"] = capabilities
    updated = item.get("updated_at") or item.get("updatedAt")
    updated_iso = timestamp_to_iso(updated)
    if updated_iso:
        normalized["updated_at"] = updated_iso
    created = item.get("created_at") or item.get("createdAt")
    created_iso = timestamp_to_iso(created)
    if created_iso:
        normalized["created_at"] = created_iso
    return normalized
