from enum import StrEnum
from typing import Any
from client import TerraformClient
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    WORKSPACE = "workspace"
    RUN = "runs"


def init_terraform_client() -> TerraformClient:
    """
    Intialize Jenkins Client
    """
    config = ocean.integration_config

    jenkins_client = TerraformClient(
                        config["terraform_host"],
                        config["terraform_organization"],
                        config["token_token"])

    return jenkins_client



# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync()
async def on_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # 1. Get all data from the source system
    # 2. Return a list of dictionaries with the raw data of the state to run the core logic of the framework for
    # Example:
    # if kind == "project":
    #     return [{"some_project_key": "someProjectValue", ...}]
    # if kind == "issues":
    #     return [{"some_issue_key": "someIssueValue", ...}]
    return []


# The same sync logic can be registered for one of the kinds that are available in the mapping in port.
@ocean.on_resync(ObjectKind.WORKSPACE)
async def resync_workspaces(kind: str) -> list[dict[Any, Any]]:
    terraform_client = init_terraform_client()

    async for workspace in terraform_client.get_paginated_workspaces():
        logger.info(f"Received ${len(workspace)} batch workspaces")
        yield workspace




# @ocean.on_resync(ObjectKind.RUN)
# async def resync_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
#     terraform_client = init_terraform_client()

#     async for workspaces in terraform_client.get_paginated_workspaces():
#         logger.info(f"Received ${len(workspace)} batch runs")
#         for workspace in workspaces:
#             async for runs in terraform_client.get_paginated_runs_for_workspace(workspace_id)
#                 yield runs


@ocean.on_resync(ObjectKind.RUN)
async def resync_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()

    async for workspaces in terraform_client.get_paginated_workspaces():
        logger.info(f"Received ${len(workspace)} batch runs")
        for workspace in workspaces:
            runs = await terraform_client.get_runs(workspace['id'])
            yield runs




# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting integration")
