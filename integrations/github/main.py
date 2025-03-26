from typing import cast

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from client import GitHubClient
from helpers.utils import ObjectKind
from webhook_processors.repository import RepositoryWebhookProcessor
from webhook_processors.pull_request import PullRequestWebhookProcessor
from webhook_processors.issue import IssueWebhookProcessor
from webhook_processors.team import TeamWebhookProcessor
from webhook_processors.workflow import WorkflowWebhookProcessor

@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration and set up webhooks."""
    logger.info("Starting Port Ocean GitHub integration")
    
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    client = GitHubClient.from_ocean_config()
    logger.info("Subscribing to GitHub webhooks")
    await client.create_webhooks_if_not_exists()



@ocean.on_resync()
async def on_global_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Handle resync for any kind."""
    if kind not in ObjectKind.available_kinds():
        logger.error(f"Kind {kind} is not supported in this integration")
        return
        
    handlers = {
        ObjectKind.REPOSITORY: resync_repositories,
        ObjectKind.PULL_REQUEST: resync_pull_requests,
        ObjectKind.ISSUE: resync_issues,
        ObjectKind.TEAM: resync_teams,
        ObjectKind.WORKFLOW: resync_workflows,
    }
    
    if handler := handlers.get(kind):
        async for items in handler(kind):
            yield items


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")
    client = GitHubClient.from_ocean_config()

    async for repositories in client.get_repositories():
        yield repositories

@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests from all repositories."""
    logger.info(f"Starting resync for kind: {kind}")
    client = GitHubClient.from_ocean_config()
    async for repositories in client.get_repositories():
        tasks = [
            client.get_pull_requests(repo["name"])
            for repo in repositories
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all issues from all repositories."""
    logger.info(f"Starting resync for kind: {kind}")
    client = GitHubClient.from_ocean_config()
    async for repositories in client.get_repositories():
        tasks = [
            client.get_issues(repo["name"])
            for repo in repositories
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all teams in the organization."""
    logger.info(f"Starting resync for kind: {kind}")
    client = GitHubClient.from_ocean_config()
    async for teams in client.get_teams():
        yield teams

@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflows from all repositories."""
    logger.info(f"Starting resync for kind: {kind}")
    client = GitHubClient.from_ocean_config()
    async for repositories in client.get_repositories():
        tasks = []
        for repo in repositories:
            async for workflows in client.get_workflows(repo["name"]):

                for workflow in workflows:
                    workflow["repository"] = repo
                    runs = await client.get_workflow_runs(repo["name"], workflow["id"], per_page=1)
                    workflow["latest_run"] = runs[0] if runs else {"status": "unknown"}
                tasks.append(workflows)
        
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", TeamWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkflowWebhookProcessor)
