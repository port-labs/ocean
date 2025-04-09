from typing import cast

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import (
    GithubIssueResourceConfig,
    GithubPullRequestResourceConfig,
    GithubRepositoryResourceConfig,
    GithubTeamResourceConfig,
    GithubWorkflowResourceConfig,
    PortGithubResources,
)
from github.client import GitHub


@ocean.on_resync(PortGithubResources.REPO)
async def get_owner_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubRepositoryResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            yield data


@ocean.on_resync(PortGithubResources.TEAM)
async def get_org_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    token = ocean.integration_config.get("github_token")
    if token is None:
        logger.error("this event only works for authenticated users")
        return

    github = GitHub(token)
    resource_config = cast(GithubTeamResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_teams(org):
            yield data


@ocean.on_resync(PortGithubResources.PR)
async def get_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubPullRequestResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            for repo in data:
                async for pr in github.get_pull_requests(
                    org, repo["name"], pr_state=selector.state
                ):
                    yield pr


@ocean.on_resync(PortGithubResources.ISSUE)
async def get_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubIssueResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            for repo in data:
                async for issue in github.get_issues(
                    org, repo["name"], state=selector.state
                ):
                    yield issue


@ocean.on_resync(PortGithubResources.WORKFLOW)
async def get_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubWorkflowResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            for repo in data:
                async for workflow in github.get_workflows(org, repo["name"]):
                    yield workflow
