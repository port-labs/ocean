import typing
from enum import StrEnum
from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from jira.client import JiraClient
from jira.overrides import JiraIssueConfig, JiraProjectResourceConfig


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    USER = "user"


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

    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} issues")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    params = {}
    config = typing.cast(JiraIssueConfig, event.resource_config)

    if config.selector.jql:
        params["jql"] = config.selector.jql
        logger.info(
            f"Found JQL filter: {config.selector.jql}... Adding to request param"
        )

    if config.selector.fields:
        params["fields"] = config.selector.fields

    async for issues in client.get_paginated_issues(params):
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    async for users in client.get_paginated_users():
        logger.info(f"Received users batch with {len(users)} users")
        yield users


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    client = JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )

    webhook_event = data.get("webhookEvent")
    if not webhook_event:
        logger.error("Missing webhook event")
        return {"ok": False, "error": "Missing webhook event"}

    logger.info(f"Processing webhook event: {webhook_event}")

    match webhook_event:
        case event if event.startswith("user_"):
            account_id = data["user"]["accountId"]
            logger.debug(f"Fetching user with accountId: {account_id}")
            item = await client.get_single_user(account_id)
            kind = ObjectKind.USER
        case event if event.startswith("project_"):
            project_key = data["project"]["key"]
            logger.debug(f"Fetching project with key: {project_key}")
            item = await client.get_single_project(project_key)
            kind = ObjectKind.PROJECT
        case event if event.startswith("jira:issue_"):
            issue_key = data["issue"]["key"]
            logger.debug(f"Fetching issue with key: {issue_key}")
            item = await client.get_single_issue(issue_key)
            kind = ObjectKind.ISSUE
        case _:
            logger.error(f"Unknown webhook event type: {webhook_event}")
            return {
                "ok": False,
                "error": f"Unknown webhook event type: {webhook_event}",
            }

    if not item:
        logger.error("Failed to retrieve item")
        return {"ok": False, "error": "Failed to retrieve item"}

    logger.debug(f"Retrieved {kind} item: {item}")

    if "deleted" in webhook_event:
        logger.info(f"Unregistering {kind} item")
        await ocean.unregister_raw(kind, [item])
    else:
        logger.info(f"Registering {kind} item")
        await ocean.register_raw(kind, [item])

    logger.info(f"Webhook event '{webhook_event}' processed successfully")
    return {"ok": True}


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
