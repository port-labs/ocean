from typing import Any
from enum import StrEnum
from port_ocean.context.ocean import ocean
from client import OpenCostClient


class ObjectKind(StrEnum):
    COST = "cost"


def init_client() -> OpenCostClient:
    return OpenCostClient(
        ocean.integration_config["app_host"],
        ocean.integration_config.get("window", "today"),
    )


def process_cost_item(item: dict[str, Any]) -> list[dict[str, Any]]:
    return [value for value in item.values()]


@ocean.on_resync(ObjectKind.COST)
async def on_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    data = await client.get_cost_allocation()
    processed_data = [process_cost_item(item) for item in data]
    result = [item for sublist in processed_data for item in sublist]  ## flatten list
    return result
