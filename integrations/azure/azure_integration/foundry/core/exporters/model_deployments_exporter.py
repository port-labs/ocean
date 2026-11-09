from __future__ import annotations

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListModelDeploymentsOptions
from azure_integration.foundry.foundry_incremental import MODEL_DEPLOYMENT_INCREMENTAL
from azure_integration.foundry.helpers.utils import enrich_with_project


class ModelDeploymentsExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: ListModelDeploymentsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
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
                    dict(item),
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            if batch:
                yield batch
