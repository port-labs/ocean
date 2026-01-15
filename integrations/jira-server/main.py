from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from jira_server.overrides import JiraIssueConfig, JiraProjectConfig
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from kinds import Kinds
from initialize_client import create_jira_server_client, init_webhook_client
from jira_server.webhook_processors import (
    IssueWebhookProcessor,
    ProjectWebhookProcessor,
    UserWebhookProcessor,
)


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira Server integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    webhook_client = init_webhook_client()
    await webhook_client.create_webhook(base_url)


@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    config = cast(JiraProjectConfig, event.resource_config)
    params = {}
    # Optionally add expand parameters if the selector defines it.
    if hasattr(config, "selector") and getattr(config.selector, "expand", None):
        params["expand"] = config.selector.expand

    # Fetch all projects (no pagination in Jira Server)
    projects = await client.get_all_projects()
    logger.info(f"Fetched {len(projects)} projects")

    yield projects


@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    config = cast(JiraIssueConfig, event.resource_config)
    params = {}
    if hasattr(config, "selector") and config.selector.jql:
        params["jql"] = config.selector.jql
        logger.info(f"Using JQL: {config.selector.jql}")
    else:
        params["jql"] = "status != Done"

    async for issues in client.get_paginated_issues(params=params):
        logger.info(f"Fetched {len(issues)} issues")
        yield issues


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    async for users in client.get_paginated_users():
        logger.info(f"Fetched {len(users)} users")
        yield users


ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)
