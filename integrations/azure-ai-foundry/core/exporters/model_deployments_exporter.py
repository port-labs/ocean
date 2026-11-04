from __future__ import annotations

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.http.foundry_client import FoundryHttpClient
from clients.quota_client import create_quota_client
from core.exporters.abstract_exporter import AbstractFoundryExporter
from helpers.project_scope import enrich_with_project, get_project_endpoint
from helpers.utils import region_from_project_endpoint, timestamp_to_iso
from foundry_incremental import MODEL_DEPLOYMENT_INCREMENTAL


class ModelDeploymentsExporter(AbstractFoundryExporter[FoundryHttpClient]):
    async def get_paginated_resources(self, **_options: object) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor = active_incremental_cursor()
        params = MODEL_DEPLOYMENT_INCREMENTAL.merge_params({}, cursor)
        quota = create_quota_client()
        project_endpoint = get_project_endpoint()

        async for page in paginate_with_strategy(
            self.client.send_paginated_request(
                project_endpoint, "deployments", params=params
            ),
            cursor=cursor,
            strategy=MODEL_DEPLOYMENT_INCREMENTAL,
        ):
            check = await quota.check_before_batch(
                region=region_from_project_endpoint(project_endpoint),
                batch_size=len(page),
            )
            if not check.allowed:
                logger.warning(
                    f"Skipping deployment batch for {project_endpoint}: "
                    f"{check.message}"
                )
                continue
            yield [
                enrich_with_project(_normalize_deployment(item)) for item in page
            ]


def _normalize_deployment(item: dict[str, object]) -> dict[str, object]:
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
