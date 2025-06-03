from typing import Any

from integration.clients.github import IntegrationClient
from integration.utils.kind import ObjectKind
from integration.clients.auth import AuthClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


def init_client() -> IntegrationClient:
    # config setup
    access_token = ocean.integration_config.get("personal_access_token", None)
    org = ocean.integration_config.get("github_organization", None)
    auth_client = AuthClient(access_token=access_token, user_agent=org)
    return IntegrationClient(auth_client)


# resync all object kinds
@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    match kind:
        case ObjectKind.REPOSITORY:
            resync_repositories(kind)
        case ObjectKind.ISSUE:
            resync_issues(kind)
        case ObjectKind.WORKFLOW:
            resync_workflows(kind)
        case ObjectKind.TEAM:
            resync_teams(kind)
        case ObjectKind.PULL_REQUEST:
            resync_pull_requests(kind)

    return []


# resync repository
@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.REPOSITORY:
        client = init_client()
        async for repositories in client.get_repositories():
            yield repositories


# resync issues
@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.ISSUE:
        client = init_client()
        async for repositories in client.get_repositories():
            tasks = [
                client.get_issues(repo_slug=repo.get("name")) for repo in repositories
            ]
            async for issues in stream_async_iterators_tasks(*tasks):
                yield issues


# resync workflows
@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.WORKFLOW:
        client = init_client()
        async for repositories in client.get_repositories():
            tasks = [
                client.get_workflows(repo_slug=repo.get("name"))
                for repo in repositories
            ]
            async for workflows in stream_async_iterators_tasks(*tasks):
                yield workflows


# resync teams
@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.TEAM:
        client = init_client()
        async for teams in client.get_teams():
            yield teams


# resync pull_requests
@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.PULL_REQUEST:
        client = init_client()
        async for repositories in client.get_repositories():
            tasks = [
                client.get_pull_requests(repo_slug=repo.get("name"))
                for repo in repositories
            ]
            async for prs in stream_async_iterators_tasks(*tasks):
                yield prs
