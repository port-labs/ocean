import typing
from enum import StrEnum
from typing import Any

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import CREATE_UPDATE_WEBHOOK_EVENTS, DELETE_WEBHOOK_EVENTS, JiraClient
from integration import JiraIssueResourceConfig, JiraSprintResourceConfig


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    SPRINT = "sprint"


def initialize_client() -> JiraClient:
    return JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )


async def setup_application() -> None:
    logic_settings = ocean.integration_config
    app_host = logic_settings.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Jira"
        )
        return

    jira_client = initialize_client()

    await jira_client.create_events_webhook(
        logic_settings["app_host"],
    )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()

    async for projects in client.get_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.SPRINT)
async def on_resync_sprints(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    config = typing.cast(JiraSprintResourceConfig, event.resource_config)
    params = {"state": config.selector.state}
    async for sprints in client.get_all_sprints(params):
        logger.info(f"Received sprint batch with {len(sprints)} sprints")
        yield sprints


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    config = typing.cast(JiraIssueResourceConfig, event.resource_config)
    params = {}
    if config.selector.jql:
        params["jql"] = config.selector.jql
        logger.info(f"Found JQL filter: {config.selector.jql}")

    async for issues in client.get_all_issues(config.selector.source, params):
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    client = initialize_client()
    webhook_event: str = data.get("webhookEvent", "")
    logger.info(f"Received webhook event of type: {webhook_event}")
    ocean_action = None
    delete_action = False

    if webhook_event in DELETE_WEBHOOK_EVENTS:
        ocean_action = ocean.unregister_raw
        delete_action = True
    elif webhook_event in CREATE_UPDATE_WEBHOOK_EVENTS:
        ocean_action = ocean.register_raw

    if not ocean_action:
        logger.info("Webhook event not recognized")
        return {"ok": True}

    if "project" in webhook_event:
        logger.info(f'Received webhook event for project: {data["project"]["key"]}')
        if delete_action:
            project = data["project"]
        else:
            project = await client.get_single_project(data["project"]["key"])
        await ocean_action(ObjectKind.PROJECT, [project])
    elif "issue" in webhook_event:
        logger.info(f'Received webhook event for issue: {data["issue"]["key"]}')
        if delete_action:
            issue = data["issue"]
        else:
            issue = await client.get_single_issue(data["issue"]["key"])
        await ocean_action(ObjectKind.ISSUE, [issue])
    elif "sprint" in webhook_event:
        logger.info(f'Received webhook event for sprint: {data["sprint"]["id"]}')
        if delete_action:
            sprint = data["sprint"]
        else:
            sprint = await client.get_single_sprint(data["sprint"]["id"])
        await ocean_action(ObjectKind.SPRINT, [sprint])
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
