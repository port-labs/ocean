from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from sonarqube_integration.sonarqube_client import SonarQubeClient
import httpx

sonar_client = SonarQubeClient(
    ocean.integration_config["sonar_url"],
    ocean.integration_config["sonar_api_token"],
    ocean.integration_config["sonar_organization_id"],
    ocean.integration_config["app_host"],
)

@ocean.on_resync("cloudAnalysis")
async def on_cloud_analysis_resync(kind: str) -> list[dict[str, Any]]:
    logger.info(f"Listing Pagerduty resource: {kind}")
    async with httpx.AsyncClient() as http_client:
            return await sonar_client.get_sonarqube_cloud_analysis(http_client)


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


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    print("Starting integration")
