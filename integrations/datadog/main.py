import asyncio
from typing import Callable, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_independent_async_iterators,
)

from datadog.client import DatadogClient
from datadog.utils import ORG_ID_ENRICHMENT_KEY, enrich_batch
from datadog.core.exporters.role_exporter import ListRoleOptions
from client_manager import get_client_manager
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


MAX_CONCURRENT_CLIENTS = 100


async def _resync_across_orgs(
    build_iterator: Callable[[DatadogClient], ASYNC_GENERATOR_RESYNC_TYPE],
    context: str,
    enrich_with_org_id: bool = True,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    manager = get_client_manager()

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CLIENTS)

    def build_org_iterator(
        client: DatadogClient,
    ) -> Callable[[], ASYNC_GENERATOR_RESYNC_TYPE]:
        async def iterator() -> ASYNC_GENERATOR_RESYNC_TYPE:
            async for batch in build_iterator(client):
                if enrich_with_org_id and manager.is_multi_org:
                    enrich_batch(
                        batch,
                        enrichment_key=ORG_ID_ENRICHMENT_KEY,
                        enrichment_data=client.org_id,
                    )
                yield batch

        return iterator

    tasks = (
        semaphore_async_iterator(semaphore, build_org_iterator(client))
        for client in manager.clients
    )

    async for batch in stream_independent_async_iterators(*tasks, context=context):
        logger.info(f"{context}: received batch with {len(batch)} items")
        yield batch


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListTeamOptions.from_resource_config(
        cast(TeamResourceConfig, event.resource_config)
    )
    async for teams in _resync_across_orgs(
        lambda client: TeamExporter(client).get_paginated_resources(options),
        context="Team exporter",
    ):
        yield teams


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for users in _resync_across_orgs(
        lambda client: UserExporter(client).get_paginated_resources(),
        context="User exporter",
    ):
        yield users


@ocean.on_resync(ObjectKind.HOST)
async def on_resync_hosts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for hosts in _resync_across_orgs(
        lambda client: HostExporter(client).get_paginated_resources(),
        context="Host exporter",
    ):
        yield hosts


@ocean.on_resync(ObjectKind.MONITOR)
async def on_resync_monitors(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListMonitorOptions.from_resource_config(
        cast(MonitorResourceConfig, event.resource_config)
    )
    async for monitors in _resync_across_orgs(
        lambda client: MonitorExporter(client).get_paginated_resources(options),
        context="Monitor exporter",
    ):
        yield monitors


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListSloOptions.from_resource_config(
        cast(SLOResourceConfig, event.resource_config)
    )
    async for slos in _resync_across_orgs(
        lambda client: SloExporter(client).get_paginated_resources(options),
        context="SLO exporter",
    ):
        yield slos


@ocean.on_resync(ObjectKind.SLO_HISTORY)
async def on_resync_slo_histories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListSloHistoryOptions.from_resource_config(
        cast(SLOHistoryResourceConfig, event.resource_config)
    )
    async for histories in _resync_across_orgs(
        lambda client: SloHistoryExporter(client).get_paginated_resources(options),
        context="SLO history exporter",
    ):
        yield histories


@ocean.on_resync(ObjectKind.SERVICE)
async def on_resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for services in _resync_across_orgs(
        lambda client: ServiceExporter(client).get_paginated_resources(),
        context="Service exporter",
    ):
        yield services


@ocean.on_resync(ObjectKind.SERVICE_METRIC)
async def on_resync_service_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListServiceMetricOptions.from_resource_config(
        cast(ServiceMetricResourceConfig, event.resource_config)
    )
    async for metrics in _resync_across_orgs(
        lambda client: ServiceMetricExporter(client).get_paginated_resources(options),
        context="Service metric exporter",
    ):
        yield metrics


@ocean.on_resync(ObjectKind.SERVICE_DEPENDENCY)
async def on_resync_service_dependencies(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListServiceDependencyOptions.from_resource_config(
        cast(ServiceDependencyResourceConfig, event.resource_config)
    )
    async for dependencies in _resync_across_orgs(
        lambda client: ServiceDependencyExporter(client).get_paginated_resources(
            options
        ),
        context="Service dependency exporter",
    ):
        yield dependencies


@ocean.on_resync(ObjectKind.ROLE)
async def on_resync_roles(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    options = ListRoleOptions.from_resource_config(
        cast(RoleResourceConfig, event.resource_config)
    )
    async for roles in _resync_across_orgs(
        lambda client: RoleExporter(client).get_paginated_resources(options),
        context="Role exporter",
    ):
        yield roles


@ocean.on_resync(ObjectKind.ORGANIZATION)
async def on_resync_orgs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for orgs in _resync_across_orgs(
        lambda client: OrgExporter(client).get_paginated_resources(),
        context="Organization exporter",
        enrich_with_org_id=False,
    ):
        yield orgs


@ocean.on_start()
async def on_start() -> None:
    await get_client_manager().validate_credentials()

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
        org_id = current_integration.get("_orgId")
        if not org_id:
            logger.warning("No organization ID found for webhook setup")
            return

        webhook_client = DatadogWebhookClient(get_client_manager().clients)
        await webhook_client.upsert_webhook_setup(
            base_url=base_url,
            webhook_secret=webhook_secret,
            org_id=str(org_id),
            integration_identifier=integration_identifier,
            notification_rule_scope=notification_rule_scope,
        )


register_live_events_webhooks()
