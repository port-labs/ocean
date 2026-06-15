from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from datadog.core.exporters.role_exporter import ListRoleOptions
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
    OrgExporter,
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
    RoleResourceConfig,
    TeamResourceConfig,
    MonitorResourceConfig,
    SLOResourceConfig,
    SLOHistoryResourceConfig,
    ServiceMetricResourceConfig,
    ServiceDependencyResourceConfig,
)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        TeamExporter(client).get_paginated_resources(
            ListTeamOptions.from_resource_config(
                cast(TeamResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for teams in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (UserExporter(client).get_paginated_resources() for client in init_client())

    async for users in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (HostExporter(client).get_paginated_resources() for client in init_client())

    async for hosts in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(hosts)} hosts")
        yield hosts


@ocean.on_resync(ObjectKind.MONITOR)
async def on_resync_monitors(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        MonitorExporter(client).get_paginated_resources(
            ListMonitorOptions.from_resource_config(
                cast(MonitorResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for monitors in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(monitors)} monitors")
        yield monitors


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        SloExporter(client).get_paginated_resources(
            ListSloOptions.from_resource_config(
                cast(SLOResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for slos in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(slos)} slos")
        yield slos


@ocean.on_resync(ObjectKind.SLO_HISTORY)
async def on_resync_slo_histories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        SloHistoryExporter(client).get_paginated_resources(
            ListSloHistoryOptions.from_resource_config(
                cast(SLOHistoryResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for histories in stream_async_iterators_tasks(*tasks):
        yield histories


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        ServiceExporter(client).get_paginated_resources() for client in init_client()
    )

    async for services in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(services)} services")
        yield services


@ocean.on_resync(ObjectKind.SERVICE_METRIC)
async def on_resync_service_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        ServiceMetricExporter(client).get_paginated_resources(
            ListServiceMetricOptions.from_resource_config(
                cast(ServiceMetricResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for metrics in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(metrics)} metrics")
        yield metrics


@ocean.on_resync(ObjectKind.SERVICE_DEPENDENCY)
async def on_resync_service_dependencies(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        ServiceDependencyExporter(client).get_paginated_resources(
            ListServiceDependencyOptions.from_resource_config(
                cast(ServiceDependencyResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for dependencies in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(dependencies)} dependencies")
        yield dependencies


@ocean.on_resync(ObjectKind.ROLE)
async def on_resync_roles(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (
        RoleExporter(client).get_paginated_resources(
            ListRoleOptions.from_resource_config(
                cast(RoleResourceConfig, event.resource_config)
            )
        )
        for client in init_client()
    )

    async for roles in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(roles)} roles")
        yield roles


@ocean.on_resync(ObjectKind.ORG)
async def on_resync_orgs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    tasks = (OrgExporter(client).get_paginated_resources() for client in init_client())

    async for orgs in stream_async_iterators_tasks(*tasks):
        logger.info(f"Received batch with {len(orgs)} orgs")
        yield orgs


@ocean.on_start()
async def on_start() -> None:
    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    if base_url := ocean.app.base_url:
        webhook_secret = ocean.integration_config.get("webhook_secret")
        notification_rule_scope: str | None = ocean.integration_config.get(
            "monitor_notification_rule_scope"
        )
        integration_identifier = ocean.config.integration.identifier
        current_integration = await ocean.port_client.get_current_integration()
        org_id = str(current_integration.get("_orgId"))
        if not org_id:
            logger.warning("No organization ID found for webhook setup")
            return

        webhook_client = DatadogWebhookClient(init_client())
        await webhook_client.upsert_webhook_setup(
            base_url=base_url,
            webhook_secret=webhook_secret,
            org_id=org_id,
            integration_identifier=integration_identifier,
            notification_rule_scope=notification_rule_scope,
        )


register_live_events_webhooks()
