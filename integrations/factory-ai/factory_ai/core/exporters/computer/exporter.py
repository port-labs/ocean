from __future__ import annotations

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from factory_ai.core.exporters.abstract_exporter import AbstractFactoryExporter
from factory_ai.core.exporters.computer.models import (
    Computer,
    GetComputerOptions,
    ListComputerOptions,
    ListComputersResponse,
)

_COMPUTERS_PATH = "/api/v0/computers"


class ComputerExporter(
    AbstractFactoryExporter[ListComputerOptions, GetComputerOptions]
):
    async def get_paginated_resources(
        self, options: ListComputerOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        response = await self.client.get(
            _COMPUTERS_PATH,
            ListComputersResponse,
            params=options.to_query_params() or None,
        )
        logger.debug(
            f"Fetched Factory computers batch with {len(response.computers)} records"
        )
        yield [computer.to_raw_item() for computer in response.computers]

    async def get_resource(self, options: GetComputerOptions) -> RAW_ITEM | None:
        computer = await self.client.get_or_none(
            f"{_COMPUTERS_PATH}/{options.computer_id}",
            Computer,
        )
        return computer.to_raw_item() if computer else None
