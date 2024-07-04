from enum import StrEnum
from typing import Any, Dict

from clickup.client import ClickUpClient
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    """Sets up the application, including creating webhooks."""
    logic_settings = ocean.integration_config
    logger.warning(logic_settings)
    app_host = logic_settings.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from ClickUp"
        )
        return

    clickup_client = ClickUpClient(
        logic_settings["clickup_host"],
        logic_settings["clickup_token"],
    )

    await clickup_client.create_events_webhook(
        logic_settings["app_host"],
    )


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handles the resync for teams."""
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_token"],
    )

    async for teams in client.get_paginated_teams():
        logger.info(f"Received team batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handles the resync for projects."""
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_token"],
    )

    async for teams in client.get_paginated_teams():
        for team in teams:
            team_id = team["id"]
            async for projects in client.get_paginated_projects(team_id):
                logger.info(f"Received project batch with {len(projects)} projects")
                yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handles the resync for issues."""
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_token"],
    )

    async for teams in client.get_paginated_teams():
        for team in teams:
            team_id = team["id"]
            async for projects in client.get_paginated_projects(team_id):
                for project in projects:
                    project_id = project["id"]
                    async for issues in client.get_paginated_tasks(project_id):
                        logger.info(f"Received task batch with {len(issues)} tasks")
                        yield issues


@ocean.router.post("/webhook")
async def handle_webhook_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handles incoming webhook requests."""
    client = ClickUpClient(
        ocean.integration_config["clickup_host"],
        ocean.integration_config["clickup_token"],
    )
    logger.info(f'Received webhook event of type: {data.get("event")}')
    if "task" in data:
        logger.info(f'Received webhook event for task: {data["task"]["id"]}')
        task = await client.get_single_task(data["task"]["id"])
        await ocean.register_raw(ObjectKind.ISSUE, [task])
    logger.info("Webhook event processed")
    return {"ok": True}


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    """Handles the start of the integration."""
    logger.info("Starting Port Ocean ClickUp integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
