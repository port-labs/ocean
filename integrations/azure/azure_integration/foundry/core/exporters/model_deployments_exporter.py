from __future__ import annotations

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.clients.http.foundry_client import FoundryHttpClient
from azure_integration.foundry.core.options import ListModelDeploymentsOptions
from azure_integration.foundry.helpers.utils import enrich_with_project


class ModelDeploymentsExporter:
    def __init__(self, client: FoundryHttpClient) -> None:
        self.client = client

    async def get_paginated_resources(
        self, options: ListModelDeploymentsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # Deployments list has no order/timestamp fields — always full scan.
        project_endpoint = options.project_endpoint
        project_id = options.project_id

        async for page in self.client.send_paginated_request(
            project_endpoint, "deployments"
        ):
            yield [
                enrich_with_project(
                    item,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
