from typing import Any
from loguru import logger

from port_ocean.context.ocean import ocean

from utils import ObjectKind
from jira.client import JiraClient


# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
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
        for issue in issues:
            yield issue

    # 1. Get all data from the source system
    # 2. Return a list of dictionaries with the raw data of the state to run the core logic of the framework for
    # Example:
    # if kind == "project":
    #     return [{"some_project_key": "someProjectValue", ...}]
    # if kind == "issues":
    #     return [{"some_issue_key": "someIssueValue", ...}]


# The same sync logic can be registered for one of the kinds that are available in the mapping in port.
# @ocean.on_resync('project')
# async def resync_project(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all projects from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_project_key": "someProjectValue", ...}]
#
# @ocean.on_resync('issues')
# async def resync_issues(kind: str) -> list[dict[Any, Any]]:
#     # 1. Get all issues from the source system
#     # 2. Return a list of dictionaries with the raw data of the state
#     return [{"some_issue_key": "someIssueValue", ...}]


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    logger.info("Starting Port Ocean Jira integration")
