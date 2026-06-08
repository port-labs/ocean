from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.client_factory import create_cursor_client
from core.options_builder import (
    build_admin_options,
    build_analytics_options,
)
from exporter_factory import (
    create_ai_change_metrics_exporter,
    create_ai_commit_metrics_exporter,
    create_daily_usage_exporter,
    create_usage_events_exporter,
)
from integration import (
    CursorAiChangeMetricResourceConfig,
    CursorAiCommitMetricResourceConfig,
    CursorDailyUsageResourceConfig,
    CursorUsageEventResourceConfig,
    ObjectKind,
)


@ocean.on_resync(ObjectKind.CURSOR_AI_COMMIT_METRIC.value)
async def on_resync_ai_commit_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_ai_commit_metrics_exporter()
    selector = cast(CursorAiCommitMetricResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_analytics_options(
            start_date=selector.start_date,
            end_date=selector.end_date
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CURSOR_AI_CHANGE_METRIC.value)
async def on_resync_ai_change_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_ai_change_metrics_exporter()
    selector = cast(CursorAiChangeMetricResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_analytics_options(
            start_date=selector.start_date,
            end_date=selector.end_date
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CURSOR_DAILY_USAGE.value)
async def on_resync_daily_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_daily_usage_exporter()
    selector = cast(CursorDailyUsageResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_admin_options(
            start_date=selector.start_date,
            end_date=selector.end_date
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CURSOR_USAGE_EVENT.value)
async def on_resync_usage_events(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_usage_events_exporter()
    selector = cast(CursorUsageEventResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_admin_options(
            start_date=selector.start_date,
            end_date=selector.end_date
        )
    ):
        if page:
            yield page


_ANALYTICS_KINDS = {
    ObjectKind.CURSOR_AI_COMMIT_METRIC.value,
    ObjectKind.CURSOR_AI_CHANGE_METRIC.value,
}
_ADMIN_KINDS = {
    ObjectKind.CURSOR_DAILY_USAGE.value,
    ObjectKind.CURSOR_USAGE_EVENT.value,
}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Cursor integration")

    # A single API key may be scoped to only one of the Cursor APIs, so validate
    # connectivity only for the APIs backing the kinds the user actually enabled.
    try:
        app_config = await ocean.integration.port_app_config_handler.get_port_app_config()
        configured_kinds = {resource.kind for resource in app_config.resources}
    except Exception as exc:
        logger.warning(
            f"Could not load Port app config for startup validation, "
            f"falling back to validating the AI Code Tracking API only: {exc}"
        )
        configured_kinds = set()

    client = create_cursor_client()
    if not configured_kinds or configured_kinds & _ANALYTICS_KINDS:
        await client.validate_analytics_connection()
    if configured_kinds & _ADMIN_KINDS:
        await client.validate_admin_connection()
