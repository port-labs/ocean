from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from coralogix.clients.client_factory import ClientFactory
from coralogix.core.exporters import (
    AlertDefinitionExporter,
    CaseExporter,
    ServiceExporter,
    SloExporter,
)
from coralogix.core.options import CaseOptions, ServiceOptions, SloOptions
from coralogix.helpers.utils import ObjectKind
from integration import CaseResourceConfig, ServiceResourceConfig, SloResourceConfig


@ocean.on_resync(ObjectKind.SERVICE)
async def resync_services(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(ServiceResourceConfig, event.resource_config).selector
    options = ServiceOptions(
        window=selector.window,
        lookback=selector.lookback,
        metrics_source=selector.metrics_source,
        label_filter=selector.label_filter,
    )
    async for batch in ServiceExporter(
        ClientFactory.get_client()
    ).get_paginated_resources(options):
        logger.info(f"Yielding {len(batch)} Coralogix services")
        yield batch


@ocean.on_resync(ObjectKind.SLO)
async def resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(SloResourceConfig, event.resource_config).selector
    options = SloOptions(include_status=selector.include_status)
    async for batch in SloExporter(ClientFactory.get_client()).get_paginated_resources(
        options
    ):
        logger.info(f"Yielding {len(batch)} Coralogix SLOs")
        yield batch


@ocean.on_resync(ObjectKind.ALERT_DEFINITION)
async def resync_alert_definitions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = AlertDefinitionExporter(ClientFactory.get_client())
    async for batch in exporter.get_paginated_resources():
        logger.info(f"Yielding {len(batch)} Coralogix alert definitions")
        yield batch


@ocean.on_resync(ObjectKind.CASE)
async def resync_cases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(CaseResourceConfig, event.resource_config).selector
    options = CaseOptions(days_back=selector.days_back, statuses=selector.statuses)
    async for batch in CaseExporter(ClientFactory.get_client()).get_paginated_resources(
        options
    ):
        logger.info(f"Yielding {len(batch)} Coralogix cases")
        yield batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Coralogix integration")
