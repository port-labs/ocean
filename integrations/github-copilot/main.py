from typing import Any
from enum import StrEnum

from port_ocean.context.ocean import ocean
from clients.client_factory import create_github_client
from clients.github_endpoints import GithubEndpoints
from parsers.copilot_metrics_parser import parse
from port_ocean.context.ocean import ocean
from .clients.github_client import GitHubClient

class ObjectKind(StrEnum):
    COPILOT_TEAM_METRICS = "copilot-team-metrics"
    COPILOT_ORGANIZATION_METRICS = "copilot-organization-metrics"

@ocean.on_resync(ObjectKind.COPILOT_TEAM_METRICS)
async def on_resync_copilot_team_metrics(kind: str) -> list[dict[Any, Any]]:
   github_client = create_github_client()
   result = []
   orgs = await get_organization_names(github_client)
   for org in orgs:
       await fetchMetricsForOrgTeams(github_client, GithubEndpoints.COPILOT_TEAM_METRICS, result, org)
   return result

@ocean.on_resync(ObjectKind.COPILOT_ORGANIZATION_METRICS)
async def on_resync_copilot_organization_metrics(kind: str) -> list[dict[Any, Any]]:
   github_client = create_github_client()
   result = []
   orgs = await get_organization_names(github_client)
   for org in orgs:
        await fetch_copilot_metrics_for_organizational_unit(github_client, GithubEndpoints.COPILOT_ORGANIZATION_METRICS, result, org, None)
   return result

async def get_organization_names(github_client: GitHubClient):
    if ocean.integration_config["github_orgs"]:
        return ocean.integration_config["github_orgs"].split(",")
    return await get_org_names_from_github(github_client)

async def get_org_names_from_github(github_client: GitHubClient):
    orgs = await github_client.get_paginated_data(GithubEndpoints.LIST_TOKEN_ORGS)
    return [org["login"] for org in orgs]

async def fetchMetricsForOrgTeams(github_client: GitHubClient, endpoint: GithubEndpoints, result: list[dict[Any, Any]], org: str):
    teams = await github_client.get_paginated_data(GithubEndpoints.LIST_TEAMS, {"org": org["login"]}, ignore_status_code=[403])
    if not teams:
        return

    for team in teams:
        await fetch_copilot_metrics_for_organizational_unit(github_client, endpoint, result, org, team["slug"])

async def fetch_copilot_metrics_for_organizational_unit(github_client: GitHubClient, endpoint: GithubEndpoints, result: list[dict[Any, Any]], org: str, team: str):
    route_params = {"org": org}
    if team:
        route_params["team"] = team
    metrics = await github_client.send_api_request_with_route_params('get', endpoint, route_params, ignore_status_code=[422,403])
    parsed_data = parse(metrics, team, org)
    result.extend(parsed_data)

@ocean.on_start()
async def on_start() -> None:
    print("Starting github-copilot integration")
