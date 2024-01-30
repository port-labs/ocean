from enum import StrEnum

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import DynatraceClient


class ObjectKind(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY = "entity"


def initialize_client() -> DynatraceClient:
    return DynatraceClient(
        ocean.integration_config["dynatrace_host_url"],
        ocean.integration_config["dynatrace_api_key"],
    )


@ocean.on_resync(ObjectKind.PROBLEM)
async def on_resync_problems(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for problems in dynatrace_client.get_problems():
        logger.info(f"Received batch with {len(problems)} problems")
        yield problems


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for slos in dynatrace_client.get_slos():
        logger.info(f"Received batch with {len(slos)} SLOs")
        yield slos


@ocean.on_resync(ObjectKind.ENTITY)
async def on_resync_entities(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for entities in dynatrace_client.get_entities():
        logger.info(f"Received batch with {len(entities)} entities")
        yield entities
