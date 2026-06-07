from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import init_client
from integration import ObjectKind
from datadog.webhook.webhook_client import DatadogWebhookClient
from datadog.webhook.registry import register_live_events_webhooks
from datadog.core.exporters import (
    TeamExporter,
    UserExporter,
    HostExporter,
    MonitorExporter,
    SloExporter,
    SloHistoryExporter,
    ServiceExporter,
    ServiceMetricExporter,
    ServiceDependencyExporter,
    RoleExporter,
)
from datadog.core.exporters.team_exporter import ListTeamOptions
from datadog.core.exporters.monitor_exporter import ListMonitorOptions
from datadog.core.exporters.slo_exporter import ListSloOptions
from datadog.core.exporters.slo_history_exporter import ListSloHistoryOptions
from datadog.core.exporters.service_metric_exporter import ListServiceMetricOptions
from datadog.core.exporters.service_dependency_exporter import (
    ListServiceDependencyOptions,
)
from datadog.overrides import (
    TeamResourceConfig,
    MonitorResourceConfig,
    SLOResourceConfig,
    SLOHistoryResourceConfig,
    ServiceMetricResourceConfig,
    ServiceDependencyResourceConfig,
)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    team_exporter = TeamExporter(dd_client)

    async for teams in team_exporter.get_paginated_resources(
        ListTeamOptions.from_resource_config(
            cast(TeamResourceConfig, event.resource_config)
        )
    ):
        logger.info(f"Received batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    user_exporter = UserExporter(dd_client)

    async for users in user_exporter.get_paginated_resources():
        logger.info(f"Received batch with {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    host_exporter = HostExporter(dd_client)

    async for hosts in host_exporter.get_paginated_resources():
        logger.info(f"Received batch with {len(hosts)} hosts")
        yield hosts


@ocean.on_resync(ObjectKind.MONITOR)
async def on_resync_monitors(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    monitor_exporter = MonitorExporter(dd_client)

    async for monitors in monitor_exporter.get_paginated_resources(
        ListMonitorOptions.from_resource_config(
            cast(MonitorResourceConfig, event.resource_config)
        )
    ):
        logger.info(f"Received batch with {len(monitors)} monitors")
        yield monitors


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    slo_exporter = SloExporter(dd_client)

    async for slos in slo_exporter.get_paginated_resources(
        ListSloOptions.from_resource_config(
            cast(SLOResourceConfig, event.resource_config)
        )
    ):
        logger.info(f"Received batch with {len(slos)} slos")
        yield slos


@ocean.on_resync(ObjectKind.SLO_HISTORY)
async def on_resync_slo_histories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    slo_history_exporter = SloHistoryExporter(dd_client)

    async for histories in slo_history_exporter.get_paginated_resources(
        ListSloHistoryOptions.from_resource_config(
            cast(SLOHistoryResourceConfig, event.resource_config)
        )
    ):
        yield histories


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    service_exporter = ServiceExporter(dd_client)

    async for services in service_exporter.get_paginated_resources():
        logger.info(f"Received batch with {len(services)} services")
        yield services


@ocean.on_resync(ObjectKind.SERVICE_METRIC)
async def on_resync_service_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    service_metric_exporter = ServiceMetricExporter(dd_client)

    async for metrics in service_metric_exporter.get_paginated_resources(
        ListServiceMetricOptions.from_resource_config(
            cast(ServiceMetricResourceConfig, event.resource_config)
        )
    ):
        logger.info(f"Received batch with {len(metrics)} metrics")
        yield metrics


@ocean.on_resync(ObjectKind.SERVICE_DEPENDENCY)
async def on_resync_service_dependencies(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    service_dependency_exporter = ServiceDependencyExporter(dd_client)

    async for dependencies in service_dependency_exporter.get_paginated_resources(
        ListServiceDependencyOptions.from_resource_config(
            cast(ServiceDependencyResourceConfig, event.resource_config)
        )
    ):
        logger.info(f"Received batch with {len(dependencies)} dependencies")
        yield dependencies


@ocean.on_resync(ObjectKind.ROLE)
async def on_resync_roles(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dd_client = init_client()
    role_exporter = RoleExporter(dd_client)

    async for roles in role_exporter.get_paginated_resources():
        logger.info(f"Received batch with {len(roles)} roles")
        yield roles


@ocean.on_start()
async def on_start() -> None:
    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    if base_url := ocean.app.base_url:
        dd_client = init_client()
        webhook_secret = ocean.integration_config.get("webhook_secret")
        notification_rule_tags: list[str] | None = ocean.integration_config.get(
            "monitor_notification_rule_tags"
        )
        integration_identifier = ocean.config.integration.identifier
        current_integration = await ocean.port_client.get_current_integration()
        org_id = str(current_integration.get("_orgId"))
        if not org_id:
            logger.warning("No organization ID found for webhook setup")
            return

        webhook_client = DatadogWebhookClient(dd_client)
        await webhook_client.upsert_webhook_setup(
            base_url=base_url,
            webhook_secret=webhook_secret,
            org_id=org_id,
            integration_identifier=integration_identifier,
            notification_rule_tags=notification_rule_tags,
        )


register_live_events_webhooks()
