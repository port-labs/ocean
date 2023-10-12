from typing import Any

from client import OpenCostClient
from port_ocean.context.ocean import ocean


@ocean.on_resync("cost")
async def on_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = OpenCostClient(ocean.integration_config["opencost_host"])
    data = await client.get_cost_allocation()
    return sum([list(item.values()) for item in data], [])
