from enum import StrEnum
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from jira.client import JiraClient


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    BOARD = "board"
    SPRINT = "sprint"


async def setup_application() -> None:
    logic_settings = ocean.integration_config
    app_host = logic_settings.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Jira"
        )
        return

    jira_client = JiraClient(
        logic_settings["jira_host"],
        logic_settings["atlassian_user_email"],
        logic_settings["atlassian_user_token"],
    )

    await jira_client.create_events_webhook(
        logic_settings["app_host"],
    )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    async for boards in client.get_boards():
        logger.info(f"Received board batch with {len(boards)} boards")
        for board in boards:
            async for projects in client.get_projects(board["id"]):
                logger.info(f"Received sprint batch with {len(projects)} sprints")
                yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    async for boards in client.get_boards():
        logger.info(f"Received board batch with {len(boards)} boards")
        for board in boards:
            async for issues in client.get_issues(board["id"]):
                logger.info(f"Received issue batch with {len(issues)} issues")
                yield issues


@ocean.on_resync(ObjectKind.BOARD)
async def on_resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    async for boards in client.get_boards():
        logger.info(f"Received board batch with {len(boards)} boards")
        yield boards


@ocean.on_resync(ObjectKind.SPRINT)
async def on_resync_sprints(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    async for boards in client.get_boards():
        logger.info(f"Received board batch with {len(boards)} boards")
        for board in boards:
            async for sprints in client.get_sprints(board["id"]):
                logger.info(f"Received sprint batch with {len(sprints)} sprints")
                yield sprints


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )
    logger.info(f'Received webhook event of type: {data.get("webhookEvent")}')
    if "project" in data:
        logger.info(f'Received webhook event for project: {data["project"]["key"]}')
        project = await client.get_single_project(data["project"]["key"])
        await ocean.register_raw(ObjectKind.PROJECT, [project])
    elif "issue" in data:
        logger.info(f'Received webhook event for issue: {data["issue"]["key"]}')
        issue = await client.get_single_issue(data["issue"]["key"])
        await ocean.register_raw(ObjectKind.ISSUE, [issue])
    elif "board" in data:
        logger.info(f'Received webhook event for board: {data["board"]["id"]}')
        board = await client.get_single_board(data["board"]["id"])
        await ocean.register_raw(ObjectKind.BOARD, [board])
    elif "sprint" in data:
        logger.info(f'Received webhook event for sprint: {data["sprint"]["id"]}')
        sprint = await client.get_single_sprint(data["sprint"]["id"])
        await ocean.register_raw(ObjectKind.SPRINT, [sprint])
    logger.info("Webhook event processed")
    return {"ok": True}


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
