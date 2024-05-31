from enum import StrEnum
from typing import Any

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import OpenCostClient


class ObjectKind(StrEnum):
    COST = "cost"
    CLOUDCOST = "cloudcost"


def initialize_client() -> OpenCostClient:
    return OpenCostClient(ocean.integration_config["opencost_host"])


@ocean.on_resync(ObjectKind.COST)
async def on_cost_resync(kind: str) -> list[dict[Any, Any]]:
    client = initialize_client()
    data = await client.get_cost_allocation()
    return [value for item in data for value in item.values()]


@ocean.on_resync(ObjectKind.CLOUDCOST)
async def on_cloudcost_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    cloudcost_data = await client.get_cloudcost()
    for cloudcost in cloudcost_data:
        # data cannot be ingested by port except it is of `list` type
        data = list(cloudcost["cloudCosts"].values())
        yield data
