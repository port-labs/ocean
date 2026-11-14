import asyncio
from datetime import datetime
from itertools import batched

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datadog.overrides import SLOResourceConfig

from http import HTTPStatus

from httpx import HTTPStatusError
from loguru import logger

from datadog.client import DatadogClient
from datadog.core.exporters.restriction_policy_exporter import RestrictionPolicyExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from datadog.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from datadog.incremental import (
    CHANGED_RESTRICTION_POLICIES_AUDIT_QUERY,
    CHANGED_SLOS_AUDIT_QUERY,
    audit_event_asset_id,
    audit_events_search_body,
    restricted_resource_id,
)

SLO_ENRICHMENT_BATCH_SIZE = 10


class ListSloOptions(ListOptions["SLOResourceConfig"]):
    include_restriction_policy: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "SLOResourceConfig"
    ) -> "ListSloOptions":
        return cls(
            include_restriction_policy=resource_config.selector.include_restriction_policy
        )


class GetSloOptions(GetOptions["SLOResourceConfig"]):
    include_restriction_policy: bool = False

    @classmethod
    def from_resource_config(
        cls, resource_config: "SLOResourceConfig", *, resource_id: str
    ) -> "GetSloOptions":
        return cls(
            resource_id=resource_id,
            include_restriction_policy=resource_config.selector.include_restriction_policy,
        )


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

    async def get_changed_slos(
        self, options: ListSloOptions, incremental_cursor: datetime
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get SLOs created or modified since ``incremental_cursor``, found through audit
        events. With restriction policies on, SLOs whose restriction policy changed are
        included.
        Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
        """
        url = f"{self.client.api_url}/api/v2/audit/events/search"

        slo_ids: dict[str, None] = {}
        async for events in self._paginate_by_search_cursor(
            url, audit_events_search_body(CHANGED_SLOS_AUDIT_QUERY, incremental_cursor)
        ):
            for event in events:
                if slo_id := audit_event_asset_id(event):
                    slo_ids[slo_id] = None

        if options.include_restriction_policy:
            async for events in self._paginate_by_search_cursor(
                url,
                audit_events_search_body(
                    CHANGED_RESTRICTION_POLICIES_AUDIT_QUERY, incremental_cursor
                ),
            ):
                for event in events:
                    if slo_id := restricted_resource_id(event, "slo"):
                        slo_ids[slo_id] = None

        slos: list[dict[str, Any]] = []
        for slo_id in slo_ids:
            try:
                slo = await self.get_resource(
                    GetSloOptions(
                        resource_id=slo_id,
                        include_restriction_policy=options.include_restriction_policy,
                    )
                )
            except HTTPStatusError as e:
                if e.response.status_code != HTTPStatus.NOT_FOUND:
                    raise
                logger.warning(
                    f"Skipping SLO '{slo_id}' from audit events; it no longer exists in Datadog"
                )
                continue
            if slo:
                slos.append(slo)

        if slos:
            yield slos

    async def get_resource(self, options: GetSloOptions) -> dict[str, Any] | None:
        """Get a single SLO by ID.
        Docs: https://docs.datadoghq.com/api/latest/service-level-objectives/#get-an-slos-details
        """
        url = f"{self.client.api_url}/api/v1/slo/{options.resource_id}"
        slo_response = await self.client.send_api_request(url)
        slo = slo_response.get("data")
        if not slo:
            return None

        if not options.include_restriction_policy:
            return slo

        return await self.rp_exporter.enrich_resource_with_restriction_policy(
            "slo", slo
        )
