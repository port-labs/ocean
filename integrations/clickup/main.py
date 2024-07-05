from enum import StrEnum
from typing import Any

from loguru import logger
from client import ClickupClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    logic_settings = ocean.integration_config
    clickup_client = ClickupClient(logic_settings["clickup_api_token"])
    return clickup_client


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickupClient(
        ocean.integration_config["clickup_api_token"],
    )
    yield await client.get_teams()


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickupClient(
        ocean.integration_config["clickup_api_token"],
    )
    async for projects in client.get_lists():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickupClient(
        ocean.integration_config["clickup_api_token"],
    )
    async for issues in client.get_issues():
        logger.info(f"Received issues batch with {len(issues)} issues")
        yield issues


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting integration")
