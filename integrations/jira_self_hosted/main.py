from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from jira_server.overrides import JiraIssueConfig, JiraProjectConfig
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from kinds import Kinds
from initialize_client import create_jira_server_client


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
