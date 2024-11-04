from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import GithubClient
from utils import ObjectKind, ResourceKindsWithSpecialHandling

def init_client() -> GithubClient:
    return GithubClient(
        ocean.integration_config["gitlab_host"],
        ocean.integration_config["access_token"],
    )

# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    # 1. Get all data from the source system
    # 2. Return a list of dictionaries with the raw data of the state to run the core logic of the framework for
    # Example:
    # if kind == "project":
    #     return [{"some_project_key": "someProjectValue", ...}]
    # if kind == "issues":
    #     return [{"some_issue_key": "someIssueValue", ...}]

    # Initial stub to show complete flow, replace this with your own logic
    if kind == "async-gitlab-example-kind":
        return [
            {
                "my_custom_id": f"id_{x}",
                "my_custom_text": f"very long text with {x} in it",
                "my_special_score": x * 32 % 3,
                "my_component": f"component-{x}",
                "my_service": f"service-{x %2}",
                "my_enum": "VALID" if x % 2 == 0 else "FAILED",
            }
            for x in range(25)
        ]

    return []

@ocean.on_resync(ObjectKind.GROUP)
async def on_group_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = GithubClient.create_from_ocean_config()

    async for groups in github_client.get_groups():
        logger.info(f"Re-syncing {len(groups)} groups")
        yield groups

@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = GithubClient.create_from_ocean_config()

    async for projects in github_client.get_projects():
        logger.info(f"Re-syncing {len(projects)} projects")
        yield projects

@ocean.on_resync(ObjectKind.PROJECT)
async def on_merge_req_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = GithubClient.create_from_ocean_config()

    async for merge_requests in github_client.get_merge_requests():
        logger.info(f"Re-syncing {len(merge_requests)} merge requests")
        yield merge_requests

@ocean.on_resync(ObjectKind.ISSUE)
async def on_issue_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github_client = GithubClient.create_from_ocean_config()

    async for issues in github_client.get_issues():
        logger.info(f"Re-syncing {len(issues)} issues")
        yield issues


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting async-gitlab integration")
