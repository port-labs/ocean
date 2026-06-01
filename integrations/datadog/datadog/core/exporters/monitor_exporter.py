import asyncio
from itertools import batched
from typing import Any

from pydantic import BaseModel
from datadog.client import DatadogClient
from datadog.core.exporters.restriction_policy_exporter import RestrictionPolicyExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base_exporter import (
    PaginatedExporter,
    SingleResourceExporter,
)

MONITOR_ENRICHMENT_BATCH_SIZE = 10


class ListMonitorOptions(BaseModel):
    include_restriction_policy: bool = False


class MonitorExporter(
    PaginatedExporter[ListMonitorOptions], SingleResourceExporter[str]
):
    """Monitor exporter."""

    def __init__(self, client: DatadogClient) -> None:
        super().__init__(client)
        self.rp_exporter = RestrictionPolicyExporter(client)

    async def _enrich_with_restriction_policy(
        self, monitor: dict[str, Any]
    ) -> dict[str, Any]:
        """Enrich monitor with restriction policy."""
        policy = await self.rp_exporter.get_resource(f"monitor:{monitor['id']}")
        monitor["__restrictionPolicy"] = policy
        return monitor

    async def get_paginated_resources(
        self, options: ListMonitorOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get monitors from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-all-monitor-details
        """
        url = f"{self.client.api_url}/api/v1/monitor"

        async for monitors in self._paginate_by_page_param(
            url, data_key=None, page_param="page", size_param="page_size"
        ):
            if not options.include_restriction_policy:
                yield monitors
                continue

            for batch in batched(monitors, MONITOR_ENRICHMENT_BATCH_SIZE):
                enriched_monitors = await asyncio.gather(
                    *[
                        self._enrich_with_restriction_policy(monitor)
                        for monitor in batch
                    ]
                )
                yield enriched_monitors

    async def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        """Get a single monitor by ID.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-a-monitor-s-details
        """
        url = f"{self.client.api_url}/api/v1/monitor/{resource_id}"
        return await self.client.send_api_request(url)
