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
    create_daily_usage_exporter,
    create_team_model_usage_exporter,
    create_usage_events_exporter,
    create_user_model_usage_exporter,
)
from integration import (
    CursorDailyUsageResourceConfig,
    CursorTeamModelUsageResourceConfig,
    CursorUsageEventResourceConfig,
    CursorUserModelUsageResourceConfig,
    ObjectKind,
)


@ocean.on_resync(ObjectKind.CURSOR_TEAM_MODEL_USAGE)
async def on_resync_team_model_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_team_model_usage_exporter()
    selector = cast(CursorTeamModelUsageResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_analytics_options(
            start_date=selector.start_date, end_date=selector.end_date
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CURSOR_USER_MODEL_USAGE)
async def on_resync_user_model_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_user_model_usage_exporter()
    selector = cast(CursorUserModelUsageResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_analytics_options(
            start_date=selector.start_date, end_date=selector.end_date
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CURSOR_DAILY_USAGE)
async def on_resync_daily_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_daily_usage_exporter()
    selector = cast(CursorDailyUsageResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_admin_options(start_date=selector.start_date, end_date=selector.end_date)
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CURSOR_USAGE_EVENT)
async def on_resync_usage_events(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_usage_events_exporter()
    selector = cast(CursorUsageEventResourceConfig, event.resource_config).selector

    async for page in exporter.get_paginated_resources(
        build_admin_options(start_date=selector.start_date, end_date=selector.end_date)
    ):
        if page:
            yield page


_ANALYTICS_KINDS = {
    ObjectKind.CURSOR_TEAM_MODEL_USAGE,
    ObjectKind.CURSOR_USER_MODEL_USAGE,
}
_ADMIN_KINDS = {
    ObjectKind.CURSOR_DAILY_USAGE,
    ObjectKind.CURSOR_USAGE_EVENT,
}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Cursor integration")

    # A single API key may be scoped to only one of the Cursor APIs, so validate
    # connectivity only for the APIs backing the kinds the user actually enabled.
    app_config = await ocean.integration.port_app_config_handler.get_port_app_config()
    configured_kinds = {resource.kind for resource in app_config.resources}

    client = create_cursor_client()
    if configured_kinds & _ANALYTICS_KINDS:
        await client.validate_analytics_connection()
    if configured_kinds & _ADMIN_KINDS:
        await client.validate_admin_connection()
