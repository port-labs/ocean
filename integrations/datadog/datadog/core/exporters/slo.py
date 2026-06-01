import asyncio
from itertools import batched
from typing import Any, TypedDict

from integrations.datadog.datadog.client import DatadogClient
from integrations.datadog.datadog.core.exporters.restriction_policy import RestrictionPolicyExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base import PaginatedExporter

SLO_ENRICHMENT_BATCH_SIZE = 10

class SloListOptions(TypedDict, total=False):
    include_restriction_policy: bool


class SloExporter(PaginatedExporter[SloListOptions]):
    """SLO exporter."""
    def __init__(self, client: DatadogClient) -> None:
        super().__init__(client)
        self.rp_exporter = RestrictionPolicyExporter(client)

    async def _enrich_with_restriction_policy(self, slo: dict[str, Any]) -> dict[str, Any]:
        """Enrich SLO with restriction policy."""
        policy = await self.rp_exporter.get_resource(f"slo:{slo['id']}")
        slo["__restrictionPolicy"] = policy
        return slo

    async def get_paginated_resources(
        self, options: SloListOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get SLOs from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/service-level-objectives/#get-all-slos
        """
        url = f"{self.client.api_url}/api/v1/slo"

        async for slos in self._paginate_by_offset(url):
            if not (options or {}).get("include_restriction_policy", False):
                yield slos
                continue

            for batch in batched(slos, SLO_ENRICHMENT_BATCH_SIZE):
                enriched_slos = await asyncio.gather(*[
                    self._enrich_with_restriction_policy(slo)
                    for slo in batch
                ])
                yield enriched_slos
