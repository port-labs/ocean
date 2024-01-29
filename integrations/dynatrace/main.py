from enum import StrEnum
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from client import DynatraceClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY_TYPE = "entity_type"
    ENTITY = "entity"


def initialize_client() -> DynatraceClient:
    return DynatraceClient(
        ocean.integration_config["dynatrace_host"],
        ocean.integration_config["dynatrace_api_key"],
    )


@ocean.on_resync(ObjectKind.PROBLEM)
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for entities in dynatrace_client.get_resource(kind):
        logger.info(f"Received batch with {len(entities)} entities")
        yield entities


@ocean.on_resync(ObjectKind.SLO)
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for entities in dynatrace_client.get_resource(kind):
        logger.info(f"Received batch with {len(entities)} entities")
        yield entities


@ocean.on_resync(ObjectKind.ENTITY_TYPE)
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for entities in dynatrace_client.get_resource(kind):
        logger.info(f"Received batch with {len(entities)} entities")
        yield entities


@ocean.on_resync(ObjectKind.ENTITY)
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for entities in dynatrace_client.get_resource(kind):
        logger.info(f"Received batch with {len(entities)} entities")
        yield entities
