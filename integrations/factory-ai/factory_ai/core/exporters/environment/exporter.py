from __future__ import annotations

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from factory_ai.core.exporters.abstract_exporter import AbstractFactoryExporter
from factory_ai.core.exporters.environment.models import (
    Environment,
    GetEnvironmentOptions,
    ListEnvironmentOptions,
    ListEnvironmentsResponse,
)

_ENVIRONMENTS_PATH = "/api/v0/environments"


class EnvironmentExporter(
    AbstractFactoryExporter[ListEnvironmentOptions, GetEnvironmentOptions]
):
    async def get_paginated_resources(
        self, options: ListEnvironmentOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        response = await self.client.get(
            _ENVIRONMENTS_PATH,
            ListEnvironmentsResponse,
            params=options.to_query_params() or None,
        )
        logger.debug(
            f"Fetched Factory environments batch with {len(response.environments)} records"
        )
        yield [environment.to_raw_item() for environment in response.environments]

    async def get_resource(self, options: GetEnvironmentOptions) -> RAW_ITEM | None:
        environment = await self.client.get_or_none(
            f"{_ENVIRONMENTS_PATH}/{options.environment_id}",
            Environment,
        )
        return environment.to_raw_item() if environment else None
