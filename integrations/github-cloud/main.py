from typing import Any, cast

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor
from client import get_client

from integration import (
    RepositoryResourceConfig,
    IssueResourceConfig,
    PullRequestResourceConfig,
    TeamResourceConfig,
    WorkflowResourceConfig,
    ObjectKind,
)


@ocean.on_start()
async def on_start() -> None:
    """Handle integration start."""
    logger.info("Starting GitHub Cloud integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    client = get_client()
    logger.info("Subscribing to GitHub webhooks")
    await client.create_webhooks_if_not_exists()

    # Register webhook processors
    webhook_processors = [
        RepositoryWebhookProcessor,
        IssueWebhookProcessor,
        PullRequestWebhookProcessor,
        TeamWebhookProcessor,
        WorkflowWebhookProcessor,
    ]

    for processor in webhook_processors:
        ocean.add_webhook_processor("/webhook", processor)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repository(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync repositories."""
    client = get_client()

    selector = cast(RepositoryResourceConfig, event.resource_config).selector
    async for repo in client.get_repositories(selector.organizations):
        logger.info(
            f"Fetching repositories {repo['name']} for organizations: {selector.organizations}"
        )
        yield repo


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync issues."""
    client = get_client()
    selector = cast(IssueResourceConfig, event.resource_config).selector
    async for repo in client.get_repositories(selector.organizations):
        async for issue in client.get_issues(repo["owner"]["login"], repo["name"]):
            logger.info(f"Yielding issue: {issue['title']}")
            yield issue


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync pull requests."""
    client = get_client()
    selector = cast(PullRequestResourceConfig, event.resource_config).selector
    async for repo in client.get_repositories(selector.organizations):
        async for pull_request in client.get_pull_requests(
            repo["owner"]["login"], repo["name"]
        ):
            logger.info(f"Yielding pull request: {pull_request['title']}")
            yield pull_request


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync teams."""
    client = get_client()
    selector = cast(TeamResourceConfig, event.resource_config).selector
    async for repo in client.get_repositories(selector.organizations):
        async for team in client.get_teams(repo["owner"]["login"], repo["name"]):
            logger.info(f"Yielding team: {team['name']}")
            yield team


@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync workflows."""
    client = get_client()
    selector = cast(WorkflowResourceConfig, event.resource_config).selector
    async for repo in client.get_repositories(selector.organizations):
        async for workflow in client.get_workflows(
            repo["owner"]["login"], repo["name"]
        ):
            if "name" in workflow:
                logger.info(f"Yielding workflow: {workflow['name']}")
                yield workflow
            else:
                logger.warning(f"Unexpected workflow structure: {workflow}")
