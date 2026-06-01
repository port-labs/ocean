from typing import Any, AsyncGenerator, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import DatadogClient
from client_manager import DatadogClientManager
from helpers.multi_org import iterate_per_organization
from integration import ObjectKind
from overrides import (
    SLOHistoryResourceConfig,
    ServiceMetricResourceConfig,
    ServiceMetricSelector,
    TeamResourceConfig,
    ServiceDependencyResourceConfig,
)
from utils import (
    get_start_of_the_day_in_seconds_x_day_back,
    get_start_of_the_month_in_seconds_x_months_back,
)
from webhook_processors.monitor_webhook_processor import MonitorWebhookProcessor
from webhook_processors.service_dependency_webhook_processor import (
    ServiceDependencyWebhookProcessor,
)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(TeamResourceConfig, event.resource_config).selector

    async def _get_teams(client: DatadogClient) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in client.get_teams():
            if selector.include_members:
                for team in teams:
                    members: list[dict[str, Any]] = []
                    async for member_batch in client.get_team_members(team["id"]):
                        members.extend(member_batch)
                    team["__members"] = members
            yield teams

    async for teams in iterate_per_organization(_get_teams):
        logger.info(f"Received teams batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for users in iterate_per_organization(
        lambda client: client.get_users()
    ):
        logger.info(f"Received batch with {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for hosts in iterate_per_organization(
        lambda client: client.get_hosts()
    ):
        logger.info(f"Received batch with {len(hosts)} hosts")
        yield hosts


@ocean.on_resync(ObjectKind.MONITOR)
async def on_resync_monitors(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for monitors in iterate_per_organization(
        lambda client: client.get_monitors()
    ):
        logger.info(f"Received batch with {len(monitors)} monitors")
        yield monitors


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for slos in iterate_per_organization(
        lambda client: client.get_slos()
    ):
        logger.info(f"Received batch with {len(slos)} slos")
        yield slos


@ocean.on_resync(ObjectKind.SLO_HISTORY)
async def on_resync_slo_histories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
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

    async def _get_slo_histories(client: DatadogClient) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for histories in client.list_slo_histories(
            timeframe=timeframe,
            start_timestamp=start_timestamp,
            concurrency=concurrency,
        ):
            yield histories

    async for histories in iterate_per_organization(_get_slo_histories):
        yield histories


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for services in iterate_per_organization(
        lambda client: client.get_services()
    ):
        logger.info(f"Received batch with {len(services)} services")
        yield services


@ocean.on_resync(ObjectKind.SERVICE_METRIC)
async def on_resync_service_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    params: ServiceMetricSelector = cast(
        ServiceMetricResourceConfig, event.resource_config
    ).selector.metric_selector

    async def _get_metrics(client: DatadogClient) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for metrics in client.get_metrics(
            metric_query=params.metric,
            env_tag=params.env.tag,
            env_value=params.env.value,
            service_tag=params.service.tag,
            service_value=params.service.value,
            time_window_in_minutes=params.timeframe,
        ):
            yield metrics

    async for metrics in iterate_per_organization(_get_metrics):
        logger.info(f"Received batch with {len(metrics)} metrics")
        yield metrics


@ocean.on_resync(ObjectKind.SERVICE_DEPENDENCY)
async def on_resync_service_dependencies(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(ServiceDependencyResourceConfig, event.resource_config).selector

    async def _get_dependencies(client: DatadogClient) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for dependencies in client.get_service_dependencies(
            env=selector.environment, start_time=selector.start_time
        ):
            yield dependencies

    async for dependencies in iterate_per_organization(_get_dependencies):
        logger.info(f"Received batch with {len(dependencies)} dependencies")
        yield dependencies


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if base_url := ocean.app.base_url:
        manager = DatadogClientManager._build_from_config()
        for client, meta in manager.get_clients_with_meta():
            webhook_secret = meta.get("webhook_secret") or ocean.integration_config.get(
                "webhook_secret"
            )
            org_name = meta.get("org_name", "unknown")
            logger.info(f"Setting up webhooks for org: {org_name}")
            await client.create_webhooks_if_not_exists(base_url, webhook_secret)


ocean.add_webhook_processor("/webhook", MonitorWebhookProcessor)
ocean.add_webhook_processor("/webhook", ServiceDependencyWebhookProcessor)
