from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger
from amplication.client import AmplicationClient
from enum import StrEnum


class ObjectKind(StrEnum):
    TEMPLATE = "amplication_template"
    RESOURCE = "amplication_resource"
    ALERT = "amplication_alert"


def init_client() -> AmplicationClient:
    return AmplicationClient(
        ocean.integration_config["amplication_host"],
        ocean.integration_config["amplication_token"],
    )


@ocean.on_resync(ObjectKind.TEMPLATE)
async def resync_templates(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    templates = await client.get_templates()
    yield templates


@ocean.on_resync(ObjectKind.RESOURCE)
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    resources = await client.get_resources()
    yield resources


@ocean.on_resync(ObjectKind.ALERT)
async def resync_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    resources = await client.get_alerts()
    yield resources


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Amplication integration")
