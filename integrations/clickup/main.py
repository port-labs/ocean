from enum import StrEnum


from loguru import logger

from port_ocean.context.ocean import ocean

from client import ClickUpClient

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    client = ClickUpClient(
        ocean.integration_config["click_up_token"],
    )

    async for teams in client.get_teams():

        yield teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_project(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    client = ClickUpClient(
        ocean.integration_config["click_up_token"],
    )

    async for projects in client.get_projects():

        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickUpClient(
        ocean.integration_config["click_up_token"],
    )

    async for issues in client.get_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")

        yield issues


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # await setup_application()
