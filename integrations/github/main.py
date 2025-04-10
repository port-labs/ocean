import traceback
from typing import cast, Annotated

from loguru import logger
from port_ocean.context.ocean import ocean
from fastapi import Header, Request
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


from integration import (
    GithubIssueResourceConfig,
    GithubPullRequestResourceConfig,
    GithubRepositoryResourceConfig,
    GithubWorkflowResourceConfig,
)
from client import GitHub
from utils import PortGithubResources
from webhooks import GithubIssueWebhookHandler, GithubPRWebhookHandler


def create_github_client() -> GitHub:
    github = GitHub(ocean.integration_config.get("github_token"))
    return github


async def setup_application(app_host: str) -> None:
    gitHub = create_github_client()
    orgs: list[str] = ocean.integration_config.get("orgs", "").split(",")
    try:
        await gitHub.configure_webhooks(app_host, orgs=orgs)
    except Exception as e:
        logger.error("error occured while configuring webhooks.")
        logger.error(e)
        traceback.print_exc()


@ocean.on_resync(PortGithubResources.REPO)
async def get_owner_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    orgs = ocean.integration_config.get("orgs", "").split(",")
    selector = cast(GithubRepositoryResourceConfig, event.resource_config).selector
    tasks = (github.get_repositories(org, repo_type=selector.repo_type) for org in orgs)
    async for data in stream_async_iterators_tasks(*tasks):
        yield data


@ocean.on_resync(PortGithubResources.TEAM)
async def get_org_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    orgs = ocean.integration_config.get("orgs", "").split(",")
    for org in orgs:
        async for data in github.get_teams(org):
            yield data


@ocean.on_resync(PortGithubResources.PR)
async def get_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    resource_config = cast(GithubPullRequestResourceConfig, event.resource_config)
    orgs = ocean.integration_config.get("orgs", "").split(",")
    selector = resource_config.selector
    for org in orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            tasks = (
                github.get_pull_requests(org, repo["name"], pr_state=selector.state)
                for repo in data
            )
            async for pr in stream_async_iterators_tasks(*tasks):
                yield pr


@ocean.on_resync(PortGithubResources.ISSUE)
async def get_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    resource_config = cast(GithubIssueResourceConfig, event.resource_config)
    orgs = ocean.integration_config.get("orgs", "").split(",")
    selector = resource_config.selector
    for org in orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            tasks = (
                github.get_issues(org, repo["name"], state=selector.state)
                for repo in data
            )
            async for issue in stream_async_iterators_tasks(*tasks):
                yield issue


@ocean.on_resync(PortGithubResources.WORKFLOW)
async def get_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubWorkflowResourceConfig, event.resource_config)
    selector = resource_config.selector
    orgs = ocean.integration_config.get("orgs", "").split(",")
    for org in orgs:
        async for data in github.get_repositories(org, repo_type=selector.repo_type):
            tasks = (github.get_workflows(org, repo["name"]) for repo in data)
            async for workflow in stream_async_iterators_tasks(*tasks):
                yield workflow


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Github integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    app_host = ocean.integration_config.get("app_host")
    if not app_host:
        return

    await setup_application(app_host)


@ocean.router.post("/webhook")
async def webhook(
    X_GitHub_Event: Annotated[str | None, Header()], request: Request
) -> None:
    body = await request.json()
    match X_GitHub_Event:
        case "issues":
            await GithubIssueWebhookHandler().handle_event(body)
        case "pull_request":
            await GithubPRWebhookHandler().handle_event(body)
