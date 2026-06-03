import asyncio
from itertools import batched

from pydantic import BaseModel
from typing import Any
from datadog.client import DatadogClient
from datadog.core.exporters.restriction_policy_exporter import RestrictionPolicyExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base_exporter import PaginatedExporter, SingleResourceExporter

SLO_ENRICHMENT_BATCH_SIZE = 10


class ListSloOptions(BaseModel):
    include_restriction_policy: bool = False


class GetSloOptions(BaseModel):
    id: str
    include_restriction_policy: bool = False


class SloExporter(
    PaginatedExporter[ListSloOptions], SingleResourceExporter[GetSloOptions]
):
    """SLO exporter."""

    def __init__(self, client: DatadogClient) -> None:
        super().__init__(client)
        self.rp_exporter = RestrictionPolicyExporter(client)

    async def get_paginated_resources(
        self, options: ListSloOptions = ListSloOptions()
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get SLOs from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/service-level-objectives/#get-all-slos
        """
        url = f"{self.client.api_url}/api/v1/slo"

        async for slos in self._paginate_by_offset(url):
            if not options.include_restriction_policy:
                yield slos
                continue

            for batch in batched(slos, SLO_ENRICHMENT_BATCH_SIZE):
                enriched_slos = await asyncio.gather(
                    *[
                        self.rp_exporter.enrich_resource_with_restriction_policy(
                            "slo", slo
                        )
                        for slo in batch
                    ]
                )
                yield enriched_slos

    async def get_resource(self, resource_id: GetSloOptions) -> dict[str, Any] | None:
        """Get a single SLO by ID.
        Docs: https://docs.datadoghq.com/api/latest/service-level-objectives/#get-an-slos-details
        """
        url = f"{self.client.api_url}/api/v1/slo/{resource_id.id}"
        slo_response = await self.client.send_api_request(url)
        slos = slo_response.get("data", [])
        slo = slos[0] if slos else None
        if not slo:
            return None

        if not resource_id.include_restriction_policy:
            return slo

        return await self.rp_exporter.enrich_resource_with_restriction_policy("slo", slo)
