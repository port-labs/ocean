from enum import StrEnum
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from clickup.handler import ClickUpPortHandler

class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"

@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    handler = ClickUpPortHandler()
    async for teams in handler.fetch_teams():
        logger.info(f"Received team batch with {len(teams)} teams")
        yield teams

@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    handler = ClickUpPortHandler()
    async for projects, team_id in handler.fetch_all_projects():
        logger.info(f"Received projects batch with {len(projects)} projects for team {team_id}")
        yield projects

@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    handler = ClickUpPortHandler()
    async for tasks in handler.fetch_issues():
        yield tasks

@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")