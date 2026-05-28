from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.options_builder import (
    build_activity_summary_options,
    build_cost_options,
    build_usage_options,
    build_user_activity_options,
    build_user_cost_report_options,
    build_user_usage_report_options,
    get_daily_dates,
)
from exporter_factory import (
    create_activity_summary_exporter,
    create_cost_exporter,
    create_usage_exporter,
    create_user_activity_exporter,
    create_user_cost_report_exporter,
    create_user_usage_report_exporter,
)
from integration import (
    ClaudeActivitySummaryResourceConfig,
    ClaudeCostRecordResourceConfig,
    ClaudeUsageRecordResourceConfig,
    ClaudeUserActivityResourceConfig,
    ClaudeUserCostReportResourceConfig,
    ClaudeUserUsageReportResourceConfig,
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
            group_by=cost_selector.group_by,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_USER_ACTIVITY.value)
async def on_resync_user_activity(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    activity_selector = cast(
        ClaudeUserActivityResourceConfig, event.resource_config
    ).selector
    exporter = create_user_activity_exporter()

    dates = get_daily_dates(
        starting_date=activity_selector.starting_date,
        time_frame=activity_selector.time_frame,
    )
    logger.info(f"Fetching Claude user activity for {len(dates)} day(s)")

    for day in dates:
        async for page in exporter.get_paginated_resources(
            build_user_activity_options(date=day)
        ):
            if page:
                yield page


@ocean.on_resync(ObjectKind.CLAUDE_ACTIVITY_SUMMARY.value)
async def on_resync_activity_summary(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    summary_selector = cast(
        ClaudeActivitySummaryResourceConfig, event.resource_config
    ).selector
    exporter = create_activity_summary_exporter()

    async for page in exporter.get_paginated_resources(
        build_activity_summary_options(
            starting_date=summary_selector.starting_date,
            ending_date=summary_selector.ending_date,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_USER_USAGE_REPORT.value)
async def on_resync_user_usage_report(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    usage_selector = cast(
        ClaudeUserUsageReportResourceConfig, event.resource_config
    ).selector
    exporter = create_user_usage_report_exporter()

    async for page in exporter.get_paginated_resources(
        build_user_usage_report_options(
            starting_date=usage_selector.starting_date,
            ending_date=usage_selector.ending_date,
            group_by=usage_selector.group_by,
            order_by=usage_selector.order_by,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_USER_COST_REPORT.value)
async def on_resync_user_cost_report(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    cost_selector = cast(
        ClaudeUserCostReportResourceConfig, event.resource_config
    ).selector
    exporter = create_user_cost_report_exporter()

    async for page in exporter.get_paginated_resources(
        build_user_cost_report_options(
            starting_date=cost_selector.starting_date,
            ending_date=cost_selector.ending_date,
            group_by=cost_selector.group_by,
            order_by=cost_selector.order_by,
        )
    ):
        if page:
            yield page


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Claude integration")
