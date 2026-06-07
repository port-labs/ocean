import asyncio
from itertools import batched
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from datadog.overrides import MonitorResourceConfig

from datadog.client import DatadogClient
from datadog.core.exporters.restriction_policy_exporter import RestrictionPolicyExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

MONITOR_ENRICHMENT_BATCH_SIZE = 10


class ListMonitorOptions(ListOptions):
    include_restriction_policy: bool = False

    @classmethod
    def from_resource_config(cls, resource_config: "MonitorResourceConfig") -> "ListMonitorOptions":
        return cls(include_restriction_policy=resource_config.selector.include_restriction_policy)


class GetMonitorOptions(GetOptions):
    resource_id: str
    include_restriction_policy: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "MonitorResourceConfig", *, resource_id: str
    ) -> "GetMonitorOptions":
        return cls(
            resource_id=resource_id,
            include_restriction_policy=resource_config.selector.include_restriction_policy,
        )


class MonitorExporter(
    PaginatedExporter[ListMonitorOptions], SingleResourceExporter[GetMonitorOptions]
):
    """Monitor exporter."""

    def __init__(self, client: DatadogClient) -> None:
        super().__init__(client)
        self.rp_exporter = RestrictionPolicyExporter(client)

    async def get_paginated_resources(
        self, options: ListMonitorOptions = ListMonitorOptions()
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
                        self.rp_exporter.enrich_resource_with_restriction_policy(
                            "monitor", monitor
                        )
                        for monitor in batch
                    ]
                )
                yield enriched_monitors

    async def get_resource(
        self, resource_id: GetMonitorOptions
    ) -> dict[str, Any] | None:
        """Get a single monitor by ID.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-a-monitor-s-details
        """
        url = f"{self.client.api_url}/api/v1/monitor/{resource_id.resource_id}"
        monitor = await self.client.send_api_request(url)

        if not resource_id.include_restriction_policy:
            return monitor

        return await self.rp_exporter.enrich_resource_with_restriction_policy(
            "monitor", monitor
        )
