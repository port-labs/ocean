from itertools import batched
import time
from typing import Any, TypedDict

from loguru import logger
from datadog.client import MAX_PAGE_SIZE
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base import PaginatedExporter, SingleResourceExporter

FETCH_WINDOW_TIME_IN_SECONDS = 3600


class ServiceDependencyOptions(TypedDict):
    env: str
    start_time: float


class SingleServiceDependencyOptions(TypedDict):
    env: str
    start_time: float
    service_id: str


class ServiceDependencyExporter(
    PaginatedExporter[ServiceDependencyOptions],
    SingleResourceExporter[SingleServiceDependencyOptions],
):
    async def get_paginated_resources(
        self, options: ServiceDependencyOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get service dependencies from Datadog, chunked into pages.
        Docs: https://docs.datadoghq.com/api/latest/service-dependencies/
        """
        env = options["env"]
        start_time = options["start_time"]

        end_time = int(time.time())
        start_ts = time.time() - (FETCH_WINDOW_TIME_IN_SECONDS * start_time)

        url = f"{self.client.api_url}/api/v1/service_dependencies"
        result: dict[str, Any] = await self.client.send_api_request(
            url,
            params={"env": env, "start": int(start_ts), "end": end_time},
        )

        if not result:
            return

        items: list[dict[str, Any]] = [
            {"name": name, **details} for name, details in result.items()
        ]

        for batch in batched(items, MAX_PAGE_SIZE):
            yield batch

    async def get_resource(
        self, options: SingleServiceDependencyOptions
    ) -> dict[str, Any] | None:
        """Get a single service dependency."""

        end_time = int(time.time())
        start_ts = time.time() - (FETCH_WINDOW_TIME_IN_SECONDS * options["start_time"])

        url = (
            f"{self.client.api_url}/api/v1/service_dependencies/{options['service_id']}"
        )
        result: dict[str, Any] = await self.client.send_api_request(
            url,
            params={"env": options["env"], "start": int(start_ts), "end": end_time},
        )

        if not result:
            logger.warning(
                f"No service dependencies found for service {options['service_id']} in environment {options['env']}"
            )
            return None

        return result
