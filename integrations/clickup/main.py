from enum import StrEnum

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.client import ClickUpClient


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


def get_clickup_client() -> ClickUpClient:
    return ClickUpClient(
        ocean.integration_config.get("clickup_host"),
        ocean.integration_config.get("clickup_api_key"),
    )


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_clickup_client()
    teams = await client.get_teams()
    logger.info(f"Received team batch with {len(teams)} teams")
    yield teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_clickup_client()
    projects, team_id = await client.get_all_projects()
    logger.info(
        f"Received projects batch with {len(projects)} projects for team {team_id}"
    )
    yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_clickup_client()
    async for tasks in client.get_paginated_issues():
        yield tasks


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")
