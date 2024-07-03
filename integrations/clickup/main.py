from enum import StrEnum
from loguru import logger
from clickup.client import ClickUpClient

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    """Defines the different kinds of objects in the system."""
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    """
    Sets up the application by creating necessary webhooks.

    If no app host is provided, it logs a warning and skips the webhook creation.
    """
    logic_settings = ocean.integration_config
    app_host = logic_settings.get("app_host")

    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from ClickUp."
        )
        return
    #webhook  setup goes here

@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resyncs teams from ClickUp.

    Yields:
        List of team dictionaries.
    """
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_api_key"],
    )

    async for teams in client.get_paginated_teams():
        logger.info(f"Received team batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resyncs projects from ClickUp.

    Yields:
        List of project dictionaries.
    """
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_api_key"],
    )

    async for teams in client.get_paginated_teams():
        for team in teams:
            team_id = team["id"]
            async for spaces in client.get_paginated_spaces(team_id):
                logger.info(f"Received spaces batch with {len(spaces)} spaces for team {team_id}")
                for space in spaces:
                    space_id = space["id"]
                    async for projects in client.get_paginated_projects(space_id):
                        logger.info(f"Received projects batch with {len(projects)} projects for space {space_id}")
                        yield list(map(lambda project: ClickUpClient.parse_project(project, team_id), projects))


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resyncs issues from ClickUp.

    Yields:
        List of parsed task dictionaries with updated issues.
    """
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_api_key"],
    )

    async for teams in client.get_paginated_teams():
        for team in teams:
            team_id = team["id"]
            async for spaces in client.get_paginated_spaces(team_id):
                logger.info(f"Received spaces batch with {len(spaces)} spaces for team {team_id}")
                for space in spaces:
                    space_id = space["id"]
                    async for projects in client.get_paginated_projects(space_id):
                        for project in projects:
                            project_id = project["id"]
                            async for tasks in client.get_paginated_tasks(project_id):
                                logger.info(f"Received task batch with {len(tasks)} tasks for project {project_id}")
                                yield tasks 


@ocean.on_start()
async def on_start() -> None:
    """
    Starts the Port Ocean ClickUp integration.

    Logs the start of the integration and sets up the application if necessary.
    """
    logger.info("Starting Port Ocean ClickUp integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
