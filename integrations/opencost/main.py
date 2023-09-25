from typing import Any
from enum import StrEnum
from port_ocean.context.ocean import ocean
from client import OpenCostClient

class ObjectKind(StrEnum):
    COST = "cost"

def init_client() -> OpenCostClient:
    return OpenCostClient(ocean.integration_config["app_host"], ocean.integration_config.get("window", "today"))

@ocean.on_resync(ObjectKind.COST)
async def on_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    return await client.get_cost_allocation()
