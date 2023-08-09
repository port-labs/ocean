from enum import StrEnum
from typing import Any
from loguru import logger

from port_ocean.context.ocean import ocean
from jira.client import JiraClient


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"


async def setup_application() -> None:
    logic_settings = ocean.integration_config

    jira_client = JiraClient(
        logic_settings.get("jira_host"),
        logic_settings.get("atlassian_user_email"),
        logic_settings.get("atlassian_user_token"),
    )

    await jira_client.create_real_time_updates_webhook(
        logic_settings.get("app_host"),
    )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    client = JiraClient(
        ocean.integration_config.get("jira_host"),
        ocean.integration_config.get("atlassian_user_email"),
        ocean.integration_config.get("atlassian_user_token"),
    )

    projects = await client.get_all_projects()

    return projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    client = JiraClient(
        ocean.integration_config.get("jira_host"),
        ocean.integration_config.get("atlassian_user_email"),
        ocean.integration_config.get("atlassian_user_token"),
    )

    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict):
    client = JiraClient(
        ocean.integration_config.get("jira_host"),
        ocean.integration_config.get("atlassian_user_email"),
        ocean.integration_config.get("atlassian_user_token"),
    )
    logger.info(f'Received webhook event of type: {data.get("webhookEvent")}')
    if "project" in data:
        logger.info(f'Received webhook event for project: {data["project"]["key"]}')
        project = await client.get_single_project(data["project"]["key"])
        ocean.register_raw(ObjectKind.PROJECT, [project])
    elif "issue" in data:
        logger.info(f'Received webhook event for issue: {data["issue"]["key"]}')
        issue = await client.get_single_issue(data["issue"]["key"])
        ocean.register_raw(ObjectKind.ISSUE, [issue])
    logger.info("Webhook event processed")
    return {"ok": True}


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")
    await setup_application()
