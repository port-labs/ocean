from enum import StrEnum
from typing import Any

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
        yield problems


@ocean.on_resync(ObjectKind.SLO)
async def on_resync_slos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for slos in dynatrace_client.get_slos():
        yield slos


@ocean.on_resync(ObjectKind.ENTITY)
async def on_resync_entities(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for entities in dynatrace_client.get_entities():
        yield entities


@ocean.router.post("/webhook/problem")
async def on_problem_event(event: dict[str, str | Any]) -> dict[str, bool]:
    """
    Webhook endpoint for Dynatrace problem events
    https://docs.dynatrace.com/docs/observe-and-explore/notifications-and-alerting/problem-notifications/webhook-integration
    """
    dynatrace_client = initialize_client()
    logger.info(f"Received problem event: {event}")

    if problem_id := event.get("ProblemID"):
        problem = await dynatrace_client.get_single_problem(problem_id)
        await ocean.register_raw(ObjectKind.PROBLEM, [problem])

    logger.info("Webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Dynatrace integration")
    dynatrace_client = initialize_client()
    logger.info("Performing healthcheck")
    await dynatrace_client.healthcheck()
    logger.info("Completed healthcheck")
