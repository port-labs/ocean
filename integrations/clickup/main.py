from enum import StrEnum

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import ClickupClient


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


def get_client() -> ClickupClient:
    return ClickupClient(ocean.integration_config["clickup_apikey"])


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_client()
    async for teams in client.get_teams():
        logger.info(f"Received team batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_client()
    async for projects in client.get_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_client()
    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    print("Starting integration")
