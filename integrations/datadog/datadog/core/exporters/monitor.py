from typing import Any, TypedDict

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base import PaginatedExporter, SingleResourceExporter


class MonitorListOptions(TypedDict, total=False):
    include_restriction_policy: bool


class MonitorExporter(
    PaginatedExporter[MonitorListOptions], SingleResourceExporter[str]
):
    async def get_paginated_resources(
        self, options: MonitorListOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get monitors from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-all-monitor-details
        """
        include_rp = (options or {}).get("include_restriction_policy", False)
        url = f"{self.client.api_url}/api/v1/monitor"

        async for monitors in self._paginate_by_page(
            url, data_key=None, page_param="page", size_param="page_size"
        ):
            if include_rp:
                from datadog.core.exporters.restriction_policy import (
                    RestrictionPolicyExporter,
                )

                rp_exporter = RestrictionPolicyExporter(self.client)
                for monitor in monitors:
                    policy = await rp_exporter.get_resource(f"monitor:{monitor['id']}")
                    monitor["__restrictionPolicy"] = policy

            yield monitors

    async def get_resource(self, monitor_id: str) -> dict[str, Any] | None:
        """Get a single monitor by ID.
        Docs: https://docs.datadoghq.com/api/latest/monitors/#get-a-monitor-s-details
        """
        url = f"{self.client.api_url}/api/v1/monitor/{monitor_id}"
        return await self.client.send_api_request(url)
