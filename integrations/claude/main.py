from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.claude_client import ClaudeClient, ClaudeDeployment
from clients.client_factory import create_claude_client, is_deployment_enabled
from core.options_builder import (
    build_platform_code_analytics_options,
    build_platform_cost_options,
    build_platform_usage_options,
    build_user_activity_options,
    build_user_report_options,
    get_code_analytics_dates,
    get_user_activity_dates,
)
from exporter_factory import (
    create_platform_code_analytics_exporter,
    create_platform_cost_exporter,
    create_platform_usage_exporter,
    create_user_activity_exporter,
    create_user_cost_exporter,
    create_user_usage_exporter,
)
from integration import (
    ClaudeAIUserActivityResourceConfig,
    ClaudeAIUserCostResourceConfig,
    ClaudeAIUserUsageResourceConfig,
    ClaudePlatformCodeAnalyticsResourceConfig,
    ClaudePlatformCostRecordResourceConfig,
    ClaudePlatformUsageRecordResourceConfig,
    ObjectKind,
)

# ---------------------------------------------------------------------------
# Claude AI (Enterprise) — default mode
# ---------------------------------------------------------------------------


@ocean.on_resync(ObjectKind.CLAUDE_AI_USER_ACTIVITY.value)
async def on_resync_user_activity(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not is_deployment_enabled(ClaudeDeployment.ENTERPRISE, kind):
        return

    selector = cast(ClaudeAIUserActivityResourceConfig, event.resource_config).selector
    exporter = create_user_activity_exporter()

    dates = get_user_activity_dates(
        starting_date=selector.starting_date,
        time_frame=selector.time_frame,
    )
    if not dates:
        logger.info("No Claude AI user activity dates to fetch")
        return
    logger.info(
        f"Fetching Claude AI user activity for {len(dates)} day(s) "
        f"from {dates[0]} to {dates[-1]}"
    )

    for day in dates:
        async for page in exporter.get_paginated_resources(
            build_user_activity_options(date=day)
        ):
            if page:
                yield page


@ocean.on_resync(ObjectKind.CLAUDE_AI_USER_USAGE.value)
async def on_resync_user_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not is_deployment_enabled(ClaudeDeployment.ENTERPRISE, kind):
        return

    selector = cast(ClaudeAIUserUsageResourceConfig, event.resource_config).selector
    exporter = create_user_usage_exporter()

    async for page in exporter.get_paginated_resources(
        build_user_report_options(
            starting_at=selector.starting_at,
            ending_at=selector.ending_at,
            exclude_deleted_users=selector.exclude_deleted_users,
            products=selector.products,
            models=selector.models,
            group_by=selector.group_by,
            context_windows=selector.context_windows,
            inference_geos=selector.inference_geos,
            speeds=selector.speeds,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_AI_USER_COST.value)
async def on_resync_user_cost(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not is_deployment_enabled(ClaudeDeployment.ENTERPRISE, kind):
        return

    selector = cast(ClaudeAIUserCostResourceConfig, event.resource_config).selector
    exporter = create_user_cost_exporter()

    async for page in exporter.get_paginated_resources(
        build_user_report_options(
            starting_at=selector.starting_at,
            ending_at=selector.ending_at,
            exclude_deleted_users=selector.exclude_deleted_users,
            products=selector.products,
            models=selector.models,
            group_by=selector.group_by,
            context_windows=selector.context_windows,
            inference_geos=selector.inference_geos,
            speeds=selector.speeds,
        )
    ):
        if page:
            yield page


# ---------------------------------------------------------------------------
# Claude Platform
# ---------------------------------------------------------------------------


@ocean.on_resync(ObjectKind.CLAUDE_PLATFORM_USAGE_RECORD.value)
@ocean.on_resync(ObjectKind.CLAUDE_USAGE_RECORD.value)
async def on_resync_platform_usage_records(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not is_deployment_enabled(ClaudeDeployment.PLATFORM, kind):
        return

    selector = cast(
        ClaudePlatformUsageRecordResourceConfig, event.resource_config
    ).selector
    exporter = create_platform_usage_exporter()

    async for page in exporter.get_paginated_resources(
        build_platform_usage_options(
            starting_date=selector.starting_date,
            bucket_width=selector.bucket_width,
            group_by=selector.group_by,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_PLATFORM_COST_RECORD.value)
@ocean.on_resync(ObjectKind.CLAUDE_COST_RECORD.value)
async def on_resync_platform_cost_records(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not is_deployment_enabled(ClaudeDeployment.PLATFORM, kind):
        return

    selector = cast(
        ClaudePlatformCostRecordResourceConfig, event.resource_config
    ).selector
    exporter = create_platform_cost_exporter()

    async for page in exporter.get_paginated_resources(
        build_platform_cost_options(
            starting_date=selector.starting_date,
            bucket_width=selector.bucket_width,
        )
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.CLAUDE_PLATFORM_CODE_ANALYTICS.value)
@ocean.on_resync(ObjectKind.CLAUDE_CODE_ANALYTICS.value)
async def on_resync_platform_code_analytics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not is_deployment_enabled(ClaudeDeployment.PLATFORM, kind):
        return

    selector = cast(
        ClaudePlatformCodeAnalyticsResourceConfig, event.resource_config
    ).selector
    exporter = create_platform_code_analytics_exporter()

    dates = get_code_analytics_dates(
        starting_date=selector.starting_date,
        time_frame=selector.time_frame,
    )
    logger.info(f"Fetching Claude Platform code analytics for {len(dates)} day(s)")

    for day in dates:
        async for page in exporter.get_paginated_resources(
            build_platform_code_analytics_options(starting_date=day)
        ):
            if page:
                yield page


async def _verify_api_access(client: ClaudeClient) -> None:
    """Probe a minimal request so misconfigured keys surface clearly at startup.

    Soft-fails on 401/403 (logged) instead of raising, so a transient failure or
    a misconfiguration is visible without crash-looping the integration.
    """
    if client.deployment == ClaudeDeployment.ENTERPRISE:
        dates = get_user_activity_dates(starting_date=None, time_frame=1)
        if not dates:
            return
        endpoint = "/v1/organizations/analytics/users"
        params = {"date": dates[-1], "limit": 1}
        scope = "read:analytics"
    else:
        endpoint = "/v1/organizations/usage_report/messages"
        params = {
            "starting_at": "2026-01-01T00:00:00Z",
            "limit": 1,
            "bucket_width": "1d",
        }
        scope = "api:admin"

    try:
        payload = await client.send_api_request(
            endpoint, params, soft_fail_statuses={401, 403}
        )
    except Exception as error:
        logger.warning(f"Could not verify Anthropic API access at startup: {error}")
        return

    if payload is None:
        logger.error(
            f"Anthropic API access check failed for the "
            f"'{client.deployment.value}' deployment. Verify the admin API key is "
            f"valid and carries the '{scope}' scope."
        )
    else:
        logger.info(
            f"Verified Anthropic API access for the '{client.deployment.value}' "
            "deployment."
        )


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Claude integration")
    await _verify_api_access(create_claude_client())
