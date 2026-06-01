import asyncio
from itertools import batched
from typing import Any, TypedDict

from integrations.datadog.datadog.client import DatadogClient
from integrations.datadog.datadog.core.exporters.restriction_policy import RestrictionPolicyExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base import PaginatedExporter, SingleResourceExporter

MONITOR_ENRICHMENT_BATCH_SIZE = 10

class MonitorListOptions(TypedDict, total=False):
    include_restriction_policy: bool


class MonitorExporter(
    PaginatedExporter[MonitorListOptions], SingleResourceExporter[str]
):
    """Monitor exporter."""
    def __init__(self, client: DatadogClient) -> None:
        super().__init__(client)
        self.rp_exporter = RestrictionPolicyExporter(client)

    async def _enrich_with_restriction_policy(self, monitor: dict[str, Any]) -> dict[str, Any]:
        """Enrich monitor with restriction policy."""
        policy = await self.rp_exporter.get_resource(f"monitor:{monitor['id']}")
        monitor["__restrictionPolicy"] = policy
        return monitor

    async def get_paginated_resources(
        self, options: MonitorListOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get monitors from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-all-monitor-details
        """
        include_rp = (options or {}).get("include_restriction_policy", False)
        url = f"{self.client.api_url}/api/v1/monitor"

        async for monitors in self._paginate_by_page_param(
            url, data_key=None, page_param="page", size_param="page_size"
        ):
            if not include_rp:
                yield monitors
                continue

            for batch in batched(monitors, MONITOR_ENRICHMENT_BATCH_SIZE):
                enriched_monitors = await asyncio.gather(*[
                    self._enrich_with_restriction_policy(monitor)
                    for monitor in batch
                ])
                yield enriched_monitors

    async def get_resource(self, monitor_id: str) -> dict[str, Any] | None:
        """Get a single monitor by ID.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-a-monitor-s-details
        """
        url = f"{self.client.api_url}/api/v1/monitor/{monitor_id}"
        return await self.client.send_api_request(url)
