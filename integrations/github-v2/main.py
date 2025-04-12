import traceback
from typing import cast

from loguru import logger
from port_ocean.context.ocean import ocean
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
from utils import ObjectKind, create_github_client
from webhooks import (
    GithubIssueWebhookProcessor,
    GithubPRWebhookProcessor,
    GithubRepoWebhookProcessor,
)


async def setup_application(app_host: str) -> None:
    gitHub = create_github_client()
    org = ocean.integration_config.get("org", "")
    try:
        await gitHub.configure_webhooks(app_host, org=org)
    except Exception as e:
        logger.error("error occured while configuring webhook.")
        logger.error(e)
        traceback.print_exc()
        return


@ocean.on_resync(ObjectKind.REPO)
async def get_owner_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    org = ocean.integration_config.get("org", "")
    selector = cast(GithubRepositoryResourceConfig, event.resource_config).selector
    async for data in github.get_repositories(org, repo_type=selector.repo_type):
        yield data


@ocean.on_resync(ObjectKind.TEAM)
async def get_org_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    org = ocean.integration_config.get("org", "")
    async for data in github.get_teams(org):
        yield data


@ocean.on_resync(ObjectKind.PR)
async def get_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    resource_config = cast(GithubPullRequestResourceConfig, event.resource_config)
    org = ocean.integration_config.get("org", "")
    selector = resource_config.selector
    async for data in github.get_repositories(org, repo_type=selector.repo_type):
        tasks = (
            github.get_pull_requests(org, repo["name"], pr_state=selector.state)
            for repo in data
        )
        async for pr in stream_async_iterators_tasks(*tasks):
            yield pr


@ocean.on_resync(ObjectKind.ISSUE)
async def get_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = create_github_client()
    resource_config = cast(GithubIssueResourceConfig, event.resource_config)
    org = ocean.integration_config.get("org", "")
    selector = resource_config.selector
    async for data in github.get_repositories(org, repo_type=selector.repo_type):
        tasks = (
            github.get_issues(org, repo["name"], state=selector.state) for repo in data
        )
        async for issue in stream_async_iterators_tasks(*tasks):
            yield issue


@ocean.on_resync(ObjectKind.WORKFLOW)
async def get_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    github = GitHub(ocean.integration_config.get("github_token"))
    resource_config = cast(GithubWorkflowResourceConfig, event.resource_config)
    selector = resource_config.selector
    org = ocean.integration_config.get("org", "")
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

    app_url = ocean.app.base_url
    if not app_url:
        return

    await setup_application(app_url)


ocean.add_webhook_processor("/webhook", GithubIssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", GithubPRWebhookProcessor)
ocean.add_webhook_processor("/webhook", GithubRepoWebhookProcessor)
