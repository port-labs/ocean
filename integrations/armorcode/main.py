from typing import Any, AsyncGenerator
from port_ocean.context.ocean import ocean
from loguru import logger

from initialize_client import init_armorcode_client
from integration import ObjectKind
from armorcode.core.exporters import (
    ProductExporter,
    SubProductExporter,
    FindingExporter,
)


@ocean.on_resync(ObjectKind.PRODUCT)
async def on_products_resync(
    kind: str,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_armorcode_client()
    exporter = ProductExporter(client)
    logger.info("Fetching products from Armorcode API")
    async for products_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding products batch of size: {len(products_batch)}")
        yield products_batch


@ocean.on_resync(ObjectKind.SUB_PRODUCT)
async def on_subproducts_resync(
    kind: str,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_armorcode_client()
    exporter = SubProductExporter(client)
    logger.info("Fetching all subproducts from Armorcode API")
    async for subproducts_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding subproducts batch of size: {len(subproducts_batch)}")
        yield subproducts_batch


@ocean.on_resync(ObjectKind.FINDING)
async def on_findings_resync(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_armorcode_client()
    exporter = FindingExporter(client)
    logger.info("Fetching all findings from Armorcode API")
    async for findings_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding findings batch of size: {len(findings_batch)}")
        yield findings_batch
