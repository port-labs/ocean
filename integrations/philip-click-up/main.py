from typing import Any

from port_ocean.context.ocean import ocean
from enum import StrEnum
from loguru import logger
from click_up.client import ClickUpClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_team(kind: str) -> list[dict[str, Any]]:

    client = ClickUpClient(click_up_token=ocean.integration_config("clickup_api_key"))

    teams = await client.get_teams()
    logger.info(f"Received {len(teams)} teams")

    return teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_project(kind: str) -> list[dict[str, Any]]:

    client = ClickUpClient(click_up_token=ocean.integration_config("clickup_api_key"))
    projects = await client.get_projects()
    logger.info(f"Received {len(projects)} projects")

    return projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issue(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    client = ClickUpClient(click_up_token=ocean.integration_config("clickup_api_key"))
    async for issues in client.get_issues():
        logger.info(f"Received {len(issues)} issues")

        yield issues


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Click-Up integration")
