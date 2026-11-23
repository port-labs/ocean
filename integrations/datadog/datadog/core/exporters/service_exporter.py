from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from httpx import HTTPStatusError
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from datadog.incremental import CHANGED_SERVICES_AUDIT_QUERY, service_name_from_ref

if TYPE_CHECKING:
    from datadog.overrides import ServiceResourceConfig

SCHEMA_VERSION = "v2.2"


class GetServiceOptions(GetOptions["ServiceResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "ServiceResourceConfig", *, resource_id: str
    ) -> "GetServiceOptions":
        return cls(resource_id=resource_id)


class ServiceExporter(
    PaginatedExporter[None], SingleResourceExporter[GetServiceOptions]
):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get services from Datadog.
        Docs: https://docs.datadoghq.com/api/latest/service-definition/#get-all-service-definitions
        """
        url = f"{self.client.api_url}/api/v2/services/definitions"
        async for batch in self._paginate_by_page_param(
            url, extra_params={"schema_version": SCHEMA_VERSION}
        ):
            yield batch

    async def get_changed_services(
        self, incremental_cursor: datetime
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get services created or modified since ``incremental_cursor``, found through
        audit events. Deleted services are not returned.
        Docs: https://docs.datadoghq.com/api/latest/audit/#search-audit-logs-events
        """
        names: dict[str, None] = {}
        for ref in await self._changed_asset_ids(
            CHANGED_SERVICES_AUDIT_QUERY, incremental_cursor
        ):
            if name := service_name_from_ref(ref):
                names[name] = None

        services: list[dict[str, Any]] = []
        for name in names:
            # Same schema version as the full resync, so services keep one shape
            try:
                result = await self.client.send_api_request(
                    f"{self.client.api_url}/api/v2/services/definitions/{name}",
                    params={"schema_version": SCHEMA_VERSION},
                )
            except HTTPStatusError as e:
                if e.response.status_code != HTTPStatus.NOT_FOUND:
                    raise
                logger.warning(
                    f"Skipping service '{name}' from audit events; it no longer exists in Datadog"
                )
                continue
            if service := result.get("data"):
                services.append(service)

        if services:
            yield services

    async def get_resource(self, options: GetServiceOptions) -> dict[str, Any] | None:
        """Get a single service by ID."""
        url = f"{self.client.api_url}/api/v2/services/definitions/{options.resource_id}"
        return await self.client.send_api_request(url)
