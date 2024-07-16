from typing import Any

from client import KubeCostClient
from port_ocean.context.ocean import ocean


def init_client() -> KubeCostClient:
    return KubeCostClient(
        ocean.integration_config["kubecost_host"],
        ocean.integration_config["kubecost_api_version"],
    )


@ocean.on_resync("kubesystem")
async def on_kubesystem_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    data = await client.get_kubesystem_cost_allocation()
    return [value for item in data if item is not None for value in item.values()]


@ocean.on_resync("cloud")
async def on_cloud_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    data = await client.get_cloud_cost_allocation()
    return [value for item in data for value in item.get("cloudCosts", {}).values()]


@ocean.on_start()
async def on_start() -> None:
    client = init_client()
    client.sanity_check()
