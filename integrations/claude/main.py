from collections.abc import Sequence
from typing import Any, cast

from clients.client_factory import create_claude_client
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import (
    ClaudeCodeAnalyticsResourceConfig,
    ClaudeCostRecordResourceConfig,
    ClaudeUsageRecordResourceConfig,
    ObjectKind,
)

MAX_PAGE_SIZE = 30


@ocean.on_resync(ObjectKind.CLAUDE_USAGE_RECORD.value)
async def on_resync_usage_records(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    claude_client = create_claude_client()
    usage_selector = cast(
        ClaudeUsageRecordResourceConfig, event.resource_config
    ).selector

    async for page in claude_client.get_usage_report_messages(
        _build_common_query_params(
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
    claude_client = create_claude_client()

    async for page in claude_client.get_cost_report(
        _build_common_query_params(
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
    claude_client = create_claude_client()

    async for page in claude_client.get_claude_code_report(
        _build_common_query_params(starting_date=code_selector.starting_date)
    ):
        if page:
            yield page


def _build_common_query_params(
    starting_date: str,
    bucket_width: str | None = None,
    group_by: Sequence[str] | None = None,
    limit: int = MAX_PAGE_SIZE,
) -> dict[str, Any]:
    params: dict[str, Any] = {"starting_at": starting_date, "limit": limit}
    if bucket_width:
        params["bucket_width"] = bucket_width
    if group_by:
        params["group_by[]"] = list(group_by)
    return params


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Claude integration")
