from __future__ import annotations

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListMemoryStoresOptions
from azure_integration.foundry.foundry_incremental import MEMORY_STORE_INCREMENTAL
from azure_integration.foundry.helpers.utils import enrich_with_project

_MEMORY_STORES_FEATURE = "MemoryStores=V1Preview"


class MemoryStoresExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: ListMemoryStoresOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        cursor = active_incremental_cursor()
        params = MEMORY_STORE_INCREMENTAL.merge_params({}, cursor)
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
            batch = [
                enrich_with_project(
                    dict(item),
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if batch:
                yield batch
