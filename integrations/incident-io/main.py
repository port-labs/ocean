from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from incident_io.clients.client_factory import ClientFactory
from incident_io.core.exporters import (
    IncidentExporter,
    ScheduleExporter,
    TeamExporter,
    UserExporter,
)
from incident_io.core.options import IncidentOptions, UserOptions
from incident_io.helpers.utils import ObjectKind
from integration import IncidentResourceConfig, UserResourceConfig


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(UserResourceConfig, event.resource_config).selector
    options = UserOptions(include_inactive=selector.include_inactive)
    async for batch in UserExporter(ClientFactory.get_client()).get_paginated_resources(
        options
    ):
        logger.info(f"Yielding {len(batch)} incident.io users")
        yield batch


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in TeamExporter(
        ClientFactory.get_client()
    ).get_paginated_resources():
        logger.info(f"Yielding {len(batch)} incident.io teams")
        yield batch


@ocean.on_resync(ObjectKind.SCHEDULE)
async def resync_schedules(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = ScheduleExporter(ClientFactory.get_client())
    async for batch in exporter.get_paginated_resources():
        logger.info(f"Yielding {len(batch)} incident.io schedules")
        yield batch


@ocean.on_incremental_resync(ObjectKind.INCIDENT)
@ocean.on_resync(ObjectKind.INCIDENT)
async def resync_incidents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(IncidentResourceConfig, event.resource_config).selector
    options = IncidentOptions(
        days_back=selector.days_back,
        status_categories=selector.status_categories,
        severities=selector.severities,
        include_test=selector.include_test,
    )
    # None on a full resync. Incremental runs ask for incidents updated since
    # the cursor, and never further back than daysBack.
    since = active_incremental_cursor()
    async for batch in IncidentExporter(
        ClientFactory.get_client()
    ).get_paginated_resources(options, since=since):
        logger.info(f"Yielding {len(batch)} incident.io incidents")
        yield batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting incident.io integration")
