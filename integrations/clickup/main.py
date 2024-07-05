from enum import StrEnum


from loguru import logger

from port_ocean.context.ocean import ocean

from client import ClickUpClient

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


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


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")
