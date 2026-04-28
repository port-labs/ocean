from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.options_builder import (
    build_code_analytics_options,
    build_cost_options,
    build_usage_options,
)
from exporter_factory import (
    create_code_analytics_exporter,
    create_cost_exporter,
    create_usage_exporter,
)
from integration import (
    ClaudeCodeAnalyticsResourceConfig,
    ClaudeCostRecordResourceConfig,
    ClaudeUsageRecordResourceConfig,
    ObjectKind,
)


@ocean.on_resync(ObjectKind.CLAUDE_USAGE_RECORD.value)
async def on_resync_usage_records(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_usage_exporter()
    usage_selector = cast(
        ClaudeUsageRecordResourceConfig, event.resource_config
    ).selector

    async for page in exporter.get_paginated_resources(
        build_usage_options(
            starting_date=usage_selector.starting_date,
            bucket_width=usage_selector.bucket_width,
            group_by=usage_selector.group_by,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_COST_RECORD.value)
async def on_resync_cost_records(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    cost_selector = cast(ClaudeCostRecordResourceConfig, event.resource_config).selector
    exporter = create_cost_exporter()

    async for page in exporter.get_paginated_resources(
        build_cost_options(
            starting_date=cost_selector.starting_date,
            bucket_width=cost_selector.bucket_width,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_CODE_ANALYTICS.value)
async def on_resync_code_analytics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    code_selector = cast(
        ClaudeCodeAnalyticsResourceConfig, event.resource_config
    ).selector
    exporter = create_code_analytics_exporter()

    async for page in exporter.get_paginated_resources(
        build_code_analytics_options(starting_date=code_selector.starting_date)
    ):
        if page:
            yield page


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Claude integration")
