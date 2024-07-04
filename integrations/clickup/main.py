from enum import StrEnum
from typing import Any

from loguru import logger
from clickup.client import ClickupClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    logic_settings = ocean.integration_config
    app_host = logic_settings.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Clickup"
        )
        return

    clickup_lient = ClickupClient(logic_settings["clickup_api_token"])

    # await clickup_lient.create_events_webhook(
    #     logic_settings["app_host"],
    # )

# Required
# Listen to the resync event of all the teams specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickupClient(
        ocean.integration_config["clickup_api_token"],
    )
    yield await client.get_teams()


# Required
# Listen to the resync event of all the projects specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickupClient(
        ocean.integration_config["clickup_api_token"],
    )
    async for projects in client.get_lists():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects

# Required
# Listen to the resync event of all the issue specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClickupClient(
        ocean.integration_config["clickup_api_token"],
    )
    async for issues in client.get_issues():
        logger.info(f"Received issues batch with {len(issues)} issues")
        yield issues


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting integration")
