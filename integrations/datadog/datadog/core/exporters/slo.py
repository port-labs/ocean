from typing import TypedDict

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base import PaginatedExporter


class SloListOptions(TypedDict, total=False):
    include_restriction_policy: bool


class SloExporter(PaginatedExporter[SloListOptions]):
    async def get_paginated_resources(
        self, options: SloListOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get SLOs from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/service-level-objectives/#get-all-slos
        """
        url = f"{self.client.api_url}/api/v1/slo"

        async for slos in self._paginate_by_offset(url):
            if (options or {}).get("include_restriction_policy", False):
                from datadog.core.exporters.restriction_policy import (
                    RestrictionPolicyExporter,
                )

                rp_exporter = RestrictionPolicyExporter(self.client)
                for slo in slos:
                    policy = await rp_exporter.get_resource(f"slo:{slo['id']}")
                    slo["__restrictionPolicy"] = policy

            yield slos
