import typing
from typing import cast

from initialize_client import init_client
from integration import ObjectKind
from webhook_processors.monitor_webhook_processor import MonitorWebhookProcessor
from loguru import logger

from utils import (
    get_start_of_the_day_in_seconds_x_day_back,
    get_start_of_the_month_in_seconds_x_months_back,
)
from overrides import (
    SLOHistoryResourceConfig,
    DatadogResourceConfig,
    DatadogSelector,
    TeamResourceConfig,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    selector = cast(TeamResourceConfig, event.resource_config).selector

    async for teams in dd_client.get_teams():
        logger.info(f"Received teams batch with {len(teams)} teams")
        if selector.include_members:
            for team in teams:
                members = []
                async for member_batch in dd_client.get_team_members(team["id"]):
                    members.extend(member_batch)
                team["__members"] = members
        yield teams


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for users in dd_client.get_users():
        logger.info(f"Received batch with {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for hosts in dd_client.get_hosts():
        logger.info(f"Received batch with {len(hosts)} hosts")
        yield hosts


@ocean.on_resync(ObjectKind.MONITOR)
async def on_resync_monitors(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for monitors in dd_client.get_monitors():
        logger.info(f"Received batch with {len(monitors)} monitors")
        yield monitors


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for slos in dd_client.get_slos():
        logger.info(f"Received batch with {len(slos)} slos")
        yield slos


@ocean.on_resync(ObjectKind.SLO_HISTORY)
async def on_resync_slo_histories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    resource_config = cast(SLOHistoryResourceConfig, event.resource_config)
    selector = resource_config.selector

    timeframe = selector.timeframe
    period_of_time_in_months = selector.period_of_time_in_months
    period_of_time_in_days = selector.period_of_time_in_days
    concurrency = selector.concurrency

    if period_of_time_in_days:
        logger.info(f"Fetching SLO histories for {period_of_time_in_days} days back")
        start_timestamp = get_start_of_the_day_in_seconds_x_day_back(
            period_of_time_in_days
        )
    else:
        logger.info(
            f"Fetching SLO histories for {period_of_time_in_months} months back"
        )
        start_timestamp = get_start_of_the_month_in_seconds_x_months_back(
            period_of_time_in_months
        )

    logger.info(
        f"Fetching SLO histories for timeframe {timeframe}, start_timestamp {start_timestamp}, concurrency {concurrency}"
    )

    async for histories in dd_client.list_slo_histories(
        timeframe=timeframe, start_timestamp=start_timestamp, concurrency=concurrency
    ):
        yield histories


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    async for services in dd_client.get_services():
        logger.info(f"Received batch with {len(services)} services")
        yield services


@ocean.on_resync(ObjectKind.SERVICE_METRIC)
async def on_resync_service_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()

    params: DatadogSelector = typing.cast(
        DatadogResourceConfig, event.resource_config
    ).selector.datadog_selector

    async for metrics in dd_client.get_metrics(
        metric_query=params.metric,
        env_tag=params.env.tag,
        env_value=params.env.value,
        service_tag=params.service.tag,
        service_value=params.service.value,
        time_window_in_minutes=params.timeframe,
    ):
        logger.info(f"Received batch with {len(metrics)} metrics")
        yield metrics


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if base_url := ocean.app.base_url:
        dd_client = init_client()
        webhook_secret = ocean.integration_config.get("webhook_secret")

        await dd_client.create_webhooks_if_not_exists(base_url, webhook_secret)


ocean.add_webhook_processor("/webhook", MonitorWebhookProcessor)
