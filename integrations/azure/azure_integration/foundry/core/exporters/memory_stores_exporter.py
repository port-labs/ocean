from __future__ import annotations

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.clients.quota_client import create_quota_client
from azure_integration.foundry.core.exporters.abstract_exporter import AbstractFoundryExporter
from azure_integration.foundry.foundry_incremental import MEMORY_STORE_INCREMENTAL
from azure_integration.foundry.helpers.project_scope import enrich_with_project, get_project_endpoint
from azure_integration.foundry.helpers.utils import region_from_project_endpoint, timestamp_to_iso

_MEMORY_STORES_FEATURE = "MemoryStores=V1Preview"


class MemoryStoresExporter(AbstractFoundryExporter[FoundryHttpClient]):
    async def get_paginated_resources(self, **_options: object) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor = active_incremental_cursor()
        params = MEMORY_STORE_INCREMENTAL.merge_params({}, cursor)
        quota = create_quota_client()
        project_endpoint = get_project_endpoint()
        headers = {"Foundry-Features": _MEMORY_STORES_FEATURE}

        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "memory_stores",
                params=params,
                extra_headers=headers,
            ),
            cursor=cursor,
            strategy=MEMORY_STORE_INCREMENTAL,
        ):
            check = await quota.check_before_batch(
                region=region_from_project_endpoint(project_endpoint),
                batch_size=len(page),
            )
            if not check.allowed:
                logger.warning(
                    f"Skipping memory stores batch for {project_endpoint}: "
                    f"{check.message}"
                )
                continue
            batch = [
                enrich_with_project(_normalize_memory_store(item)) for item in page
            ]
            if batch:
                yield batch


def _normalize_memory_store(item: dict[str, object]) -> dict[str, object]:
    normalized = dict(item)
    store_id = item.get("id") or item.get("name")
    if store_id is not None:
        normalized["id"] = store_id
    name = item.get("name")
    if name is not None:
        normalized["name"] = name
    created_iso = timestamp_to_iso(item.get("created_at") or item.get("createdAt"))
    if created_iso:
        normalized["created_at"] = created_iso
    if item.get("description") is not None:
        normalized["description"] = item["description"]
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        normalized["metadata"] = metadata
    return normalized
