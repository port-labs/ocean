from typing import cast
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger

from integration import GithubPullRequestResourceConfig, GithubRepositoryResourceConfig
from wrappers import GitHub
from port import PortGithubResources


@ocean.on_resync(PortGithubResources.REPO)
async def get_owner_repositories(kind) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubRepositoryResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.type):
            yield data


@ocean.on_resync(PortGithubResources.TEAM)
async def get_org_teams(kind) -> ASYNC_GENERATOR_RESYNC_TYPE:
    token = ocean.integration_config.get("github_token")
    if token is None:
        raise ValueError("This sync only works for authenticated users")

    github = GitHub(token)
    resource_config = cast(GithubRepositoryResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_teams(org):
            yield data


@ocean.on_resync(PortGithubResources.PR)
async def get_pull_requests(kind) -> ASYNC_GENERATOR_RESYNC_TYPE:
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
async def get_issues(kind) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubPullRequestResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            for repo in data:
                async for issue in github.get_issues(
                    org, repo["name"], state=selector.state
                ):
                    yield issue


@ocean.on_resync(PortGithubResources.WORKFLOW)
async def get_workflows(kind) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubPullRequestResourceConfig, event.resource_config)
    selector = resource_config.selector
    for org in selector.orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            for repo in data:
                async for workflow in github.get_workflows(org, repo["name"]):
                    yield workflow


# Optional
# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    # Something to do when the integration starts
    # For example create a client to query 3rd party services - GitHub, Jira, etc...
    logger.info("Starting github_integration integration")
