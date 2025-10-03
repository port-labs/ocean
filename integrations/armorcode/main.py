from typing import Any
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger

from armorcode.clients.client_factory import create_armorcode_client
from armorcode.core.exporters import (
    ProductExporter,
    SubProductExporter,
    FindingExporter,
)
from armorcode.helpers.utils import ObjectKind


def init_webhook_client() -> Any:
    """Create ArmorCode client with configuration from ocean context."""
    return create_armorcode_client(
        base_url=ocean.integration_config["armorcode_api_base_url"],
        api_key=ocean.integration_config["armorcode_api_key"],
    )


@ocean.on_resync(ObjectKind.PRODUCT)
async def resync_products(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all products from ArmorCode."""
    logger.info("Starting products resync")

    client = init_webhook_client()
    exporter = ProductExporter(client)
    logger.info("Fetching products from ArmorCode API")

    async for products_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding products batch of size: {len(products_batch)}")
        yield products_batch


@ocean.on_resync(ObjectKind.SUB_PRODUCT)
async def resync_subproducts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all subproducts from ArmorCode."""
    logger.info("Starting subproducts resync")

    client = init_webhook_client()
    exporter = SubProductExporter(client)
    logger.info("Fetching subproducts from ArmorCode API")

    async for subproducts_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding subproducts batch of size: {len(subproducts_batch)}")
        yield subproducts_batch


@ocean.on_resync(ObjectKind.FINDING)
async def resync_findings(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all findings from ArmorCode."""
    logger.info("Starting findings resync")

    client = init_webhook_client()
    exporter = FindingExporter(client)
    logger.info("Fetching findings from ArmorCode API")

    async for findings_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding findings batch of size: {len(findings_batch)}")
        yield findings_batch
