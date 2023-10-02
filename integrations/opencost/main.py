from typing import Any
from enum import StrEnum
from port_ocean.context.ocean import ocean
from client import OpenCostClient
import asyncio

from loguru import logger

class ObjectKind(StrEnum):
    COST = "cost"


def init_client() -> OpenCostClient:
    return OpenCostClient(
        ocean.integration_config["app_host"],
        ocean.integration_config.get("window", "today"),
    )


async def process_cost_item(
    item: dict[str, Any], semaphore: asyncio.Semaphore
) -> list[dict[str, Any]]:
    async with semaphore:
        simplified_data = []
        for key, value in item.items():
            simplified_data.append(value)
        return simplified_data


@ocean.on_resync(ObjectKind.COST)
async def on_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    data = await client.get_cost_allocation()
    semaphore = asyncio.Semaphore(5)
    tasks = [process_cost_item(item, semaphore) for item in data]
    results = await asyncio.gather(*tasks)
    return results[0]
