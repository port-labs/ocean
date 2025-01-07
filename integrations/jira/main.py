import typing
from enum import StrEnum
from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from jira.client import JiraClient
from jira.overrides import (
    JiraIssueSelector,
    JiraPortAppConfig,
    JiraProjectResourceConfig,
    JiraIssueConfig,
)


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    USER = "user"


def create_jira_client() -> JiraClient:
    """Create JiraClient with current configuration."""
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

    jira_client = create_jira_client()

    await jira_client.create_events_webhook(
        logic_settings["app_host"],
    )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} issues")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()
    params = {}
    config = cast(JiraIssueConfig, event.resource_config)

    if config.selector.jql:
        params["jql"] = config.selector.jql
        logger.info(
            f"Found JQL filter: {config.selector.jql}... Adding to request param"
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
    client = create_jira_client()

    async for users in client.get_paginated_users():
        logger.info(f"Received users batch with {len(users)} users")
        yield users


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    client = create_jira_client()

    webhook_event = data.get("webhookEvent")
    if not webhook_event:
        logger.error("Missing webhook event")
        return {"ok": False, "error": "Missing webhook event"}

    logger.info(f"Processing webhook event: {webhook_event}")

    match webhook_event:
        case event_data if event_data.startswith("user_"):
            account_id = data["user"]["accountId"]
            logger.debug(f"Fetching user with accountId: {account_id}")
            item = await client.get_single_user(account_id)
            kind = ObjectKind.USER
        case event_data if event_data.startswith("project_"):
            project_key = data["project"]["key"]
            logger.debug(f"Fetching project with key: {project_key}")
            item = await client.get_single_project(project_key)
            kind = ObjectKind.PROJECT
        case event_data if event_data.startswith("jira:issue_"):
            issue_key = data["issue"]["key"]
            logger.info(
                f"Fetching issue with key: {issue_key} and applying specified JQL filter"
            )
            resource_configs = cast(JiraPortAppConfig, event.port_app_config).resources

            matching_resource_configs_selector = [
                resource_config.selector
                for resource_config in resource_configs
                if (
                    resource_config.kind == ObjectKind.ISSUE
                    and isinstance(resource_config.selector, JiraIssueSelector)
                )
            ]

            for selector in matching_resource_configs_selector:

                params = {}

                if selector.jql:
                    params["jql"] = f"{selector.jql} AND key = {data['issue']['key']}"
                else:
                    params["jql"] = f"key = {data['issue']['key']}"

                issues: list[dict[str, Any]] = []
                async for issues in client.get_paginated_issues(params):
                    issues.extend(issues)

                if not issues:
                    logger.warning(
                        f"Issue {data['issue']['key']} not found."
                        "This is likely due to JQL filter"
                    )
                    logger.info(f"Unregistering issue {data['issue']}")
                    await ocean.unregister_raw(ObjectKind.ISSUE, [data["issue"]])
                else:
                    issue = issues[0]
                    await ocean.register_raw(ObjectKind.ISSUE, [issue])

                return {"ok": True}
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
