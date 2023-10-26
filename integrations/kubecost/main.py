from typing import Any

from client import KubeCostClient
from port_ocean.context.ocean import ocean


@ocean.on_resync("kubesystem")
async def on_kubesystem_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = KubeCostClient(ocean.integration_config["kubecost_host"])
    data = await client.get_kubesystem_cost_allocation()
    return [value for item in data for value in item.values()]


@ocean.on_resync("cloud")
async def on_cloud_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = KubeCostClient(ocean.integration_config["kubecost_host"])
    data = await client.get_cloud_cost_allocation()
    return [value for item in data for value in item["cloudCosts"].values()]


@ocean.on_start()
async def on_start() -> None:
    client = KubeCostClient(ocean.integration_config["kubecost_host"])
    client.sanity_check()
