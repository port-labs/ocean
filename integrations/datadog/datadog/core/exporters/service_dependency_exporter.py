from itertools import batched
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datadog.overrides import ServiceDependencyResourceConfig

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    MAX_PAGE_SIZE,
    PaginatedExporter,
    SingleResourceExporter,
)

FETCH_WINDOW_TIME_IN_SECONDS = 3600


class ListServiceDependencyOptions(ListOptions["ServiceDependencyResourceConfig"]):
    env: str
    start_time: float

    @classmethod
    def from_resource_config(
        cls, resource_config: "ServiceDependencyResourceConfig"
    ) -> "ListServiceDependencyOptions":
        return cls(
            env=resource_config.selector.environment,
            start_time=resource_config.selector.start_time,
        )


class GetServiceDependencyOptions(GetOptions["ServiceDependencyResourceConfig"]):
    env: str
    start_time: float
    service_id: str

    @classmethod
    def from_resource_config(
        cls, resource_config: "ServiceDependencyResourceConfig", *, id: str
    ) -> "GetServiceDependencyOptions":
        return cls(
            service_id=id,
            env=resource_config.selector.environment,
            start_time=resource_config.selector.start_time,
        )


class ServiceDependencyExporter(
    PaginatedExporter[ListServiceDependencyOptions],
    SingleResourceExporter[GetServiceDependencyOptions],
):
    async def get_paginated_resources(
        self,
        options: ListServiceDependencyOptions,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get service dependencies from Datadog, chunked into pages.
        Docs: https://docs.datadoghq.com/api/latest/service-dependencies/
        """
        end_time = int(time.time())
        start_ts = time.time() - (FETCH_WINDOW_TIME_IN_SECONDS * options.start_time)

        url = f"{self.client.api_url}/api/v1/service_dependencies"
        result: dict[str, Any] = await self.client.send_api_request(
            url,
            params={"env": options.env, "start": int(start_ts), "end": end_time},
        )

        if not result:
            return

        items: list[dict[str, Any]] = [
            {"name": name, **details} for name, details in result.items()
        ]

        for batch in batched(items, MAX_PAGE_SIZE):
            yield list(batch)

    async def get_resource(
        self, resource_id: GetServiceDependencyOptions
    ) -> dict[str, Any] | None:
        """Get a single service dependency."""

        end_time = int(time.time())
        start_ts = time.time() - (FETCH_WINDOW_TIME_IN_SECONDS * resource_id.start_time)

        url = f"{self.client.api_url}/api/v1/service_dependencies/{resource_id.service_id}"
        result: dict[str, Any] = await self.client.send_api_request(
            url,
            params={"env": resource_id.env, "start": int(start_ts), "end": end_time},
        )

        if not result:
            logger.warning(
                f"No service dependencies found for service {resource_id.service_id} in environment {resource_id.env}"
            )
            return None

        return result
