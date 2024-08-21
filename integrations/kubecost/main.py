import typing
from typing import Any

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from client import KubeCostClient
from integration import (
    CloudCostV1ResourceConfig,
    CloudCostV2ResourceConfig,
    KubecostV1ResourceConfig,
    KubecostV2ResourceConfig,
)


def init_client() -> KubeCostClient:
    return KubeCostClient(
        ocean.integration_config["kubecost_host"],
        ocean.integration_config["kubecost_api_version"],
    )


@ocean.on_resync("kubesystem")
async def on_kubesystem_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    selector = typing.cast(
        KubecostV1ResourceConfig | KubecostV2ResourceConfig, event.resource_config
    ).selector
    data = await client.get_kubesystem_cost_allocation(selector)
    return [value for item in data if item is not None for value in item.values()]


@ocean.on_resync("cloud")
async def on_cloud_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = init_client()
    selector = typing.cast(
        CloudCostV1ResourceConfig | CloudCostV2ResourceConfig, event.resource_config
    ).selector
    data = await client.get_cloud_cost_allocation(selector)
    results: list[dict[str, Any]] = []
    for item in data:
        if item.get("cloudCosts"):
            results.extend(item.values())

    return results


@ocean.on_start()
async def on_start() -> None:
    client = init_client()
    client.sanity_check()
