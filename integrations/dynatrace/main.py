from enum import StrEnum
from typing import Any, Optional

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import DynatraceClient
from oauth_client import OAuthClient


class ObjectKind(StrEnum):
    PROBLEM = "problem"
    SLO = "slo"
    ENTITY = "entity"
    USER = "user"
    GROUP = "group"
    TEAM = "team"


oauth_client: Optional[OAuthClient] = None


def initialize_client() -> DynatraceClient:
    global oauth_client
    host_url = ocean.integration_config["dynatrace_host_url"]
    api_key = ocean.integration_config["dynatrace_api_key"]

    # Optional OAuth configurations
    account_id = ocean.integration_config.get("dynatrace_account_id")
    oauth_client_id = ocean.integration_config.get("dynatrace_oauth_client_id")
    oauth_client_secret = ocean.integration_config.get("dynatrace_oauth_client_secret")

    if not oauth_client:
        if oauth_client_id and oauth_client_secret and account_id:
            oauth_client = OAuthClient(
                client_id=oauth_client_id,
                client_secret=oauth_client_secret,
                account_id=account_id,
            )

    return DynatraceClient(
        host_url=host_url, api_key=api_key, oauth_client=oauth_client
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


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for users in dynatrace_client.get_users():
        yield users


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for groups in dynatrace_client.get_groups():
        yield groups


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    dynatrace_client = initialize_client()

    async for teams in dynatrace_client.get_teams():
        yield teams


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
