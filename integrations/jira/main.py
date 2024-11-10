import typing
from enum import StrEnum
from typing import Any

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import CREATE_UPDATE_WEBHOOK_EVENTS, DELETE_WEBHOOK_EVENTS, JiraClient
from integration import JiraIssueResourceConfig, JiraIssueSelector, JiraPortAppConfig


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"


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

    async for projects in client.get_all_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_client()
    config = typing.cast(JiraIssueResourceConfig, event.resource_config).selector
    params = {}
    if config.jql:
        params["jql"] = config.jql

    if config.fields:
        params["fields"] = config.fields

    async for issues in client.get_all_issues(params):
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
            resource_configs = typing.cast(
                JiraPortAppConfig, event.port_app_config
            ).resources

            matching_resource_configs = [
                resource_config
                for resource_config in resource_configs
                if (
                    resource_config.kind == ObjectKind.ISSUE
                    and isinstance(resource_config.selector, JiraIssueSelector)
                )
            ]

            matching_resource_config = matching_resource_configs[0]

            config = typing.cast(
                JiraIssueResourceConfig, matching_resource_config
            ).selector
            params = {}
            if config.jql:
                params["jql"] = f"{config.jql} AND key = {data['issue']['key']}"
            else:
                params["jql"] = f"key = {data['issue']['key']}"
            issues = await anext(client.get_all_issues(params))
            if not issues:
                logger.warning(
                    f"Issue {data['issue']['key']} not found."
                    "This is likely due to JQL filter"
                )
                await ocean.unregister_raw(ObjectKind.ISSUE, [data["issue"]])
                return {"ok": True}
            issue = issues[0]
        await ocean_action(ObjectKind.ISSUE, [issue])
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
