# main.py

import typing
from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from jira_server.overrides import (
    JiraIssueConfig,
    JiraProjectConfig)
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from kinds import Kinds
from initialize_client import create_jira_server_client


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean integration for Jira Server")


@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    config = typing.cast(JiraProjectConfig, event.resource_config)

    async for projects in client.get_projects():
        logger.info(f"Fetched {len(projects)} projects")
        yield projects


@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    config = typing.cast(JiraIssueConfig, event.resource_config)

    jql = ""
    if hasattr(config, "selector") and config.selector.jql:
        jql = config.selector.jql
        logger.info(f"Using JQL: {jql}")

    params = {"jql": jql or "status != Done"}

    async for issues in client.get_issues(params=params):
        logger.info(f"Fetched {len(issues)} issues")
        yield issues

@ocean.on_resync(Kinds.USER)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    config = typing.cast(JiraProjectConfig, event.resource_config)

    async for projects in client.get_projects():
        logger.info(f"Fetched {len(projects)} projects")
        yield projects


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_server_client()
    # Call the new user function (non-paginated)
    users = await client.get_users()
    logger.info(f"Fetched {len(users)} users")
    yield users
