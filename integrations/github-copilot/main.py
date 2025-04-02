from typing import Any
from enum import StrEnum

from port_ocean.context.ocean import ocean
from clients.client_factory import create_github_client
from clients.github_endpoints import GithubEndpoints
from parsers.copilot_metrics_parser import parse
from port_ocean.context.ocean import ocean

class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"

@ocean.on_resync(ObjectKind.COPILOT_TEAM_METRICS)
async def on_resync_copilot_team_metrics(kind: str) -> list[dict[Any, Any]]:
   github_client = create_github_client()
   result = []
   orgs = ocean.integration_config["github_orgs"].split(",") if ocean.integration_config["github_orgs"] else await github_client.get_paginated_data(GithubEndpoints.LIST_TOKEN_ORGS)
   for org in orgs:
       teams = await github_client.get_paginated_data(GithubEndpoints.LIST_TEAMS, {"org": org["login"]}, ignore_status_code=[403])
       if teams:
        for team in teams:
           metrics = await github_client.send_api_request_with_route_params('get', GithubEndpoints.COPILOT_TEAM_METRICS, {"org": org["login"], "team": team["slug"]}, ignore_status_code=[422,403])
           parsed_data = parse(metrics, team["slug"], org["login"])
           result.extend(parsed_data)
   return result

@ocean.on_resync(ObjectKind.COPILOT_ORGANIZATION_METRICS)
async def on_resync_copilot_organization_metrics(kind: str) -> list[dict[Any, Any]]:
   github_client = create_github_client()
   result = []
   orgs = ocean.integration_config["github_orgs"].split(",") if ocean.integration_config["github_orgs"] else await github_client.get_paginated_data(GithubEndpoints.LIST_TOKEN_ORGS)
   for org in orgs:
       metrics = await github_client.send_api_request_with_route_params('get', GithubEndpoints.COPILOT_ORGANIZATION_METRICS, {"org": org["login"]}, ignore_status_code=[422,403])
       parsed_data = parse(metrics, None, org["login"])
       result.extend(parsed_data)
   return result

@ocean.on_start()
async def on_start() -> None:
    print("Starting github-copilot integration")
