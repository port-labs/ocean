from typing import cast

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from client import GitHubClient
from helpers.utils import ObjectKind
from integration import GitHubResourceConfig

@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean GitHub integration")

def init_client() -> GitHubClient:
    return GitHubClient(
        token=ocean.integration_config.get_secret("github_token"),
        org=ocean.integration_config.get("organization")
    )

@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    client = init_client()
    async for repositories in client.get_repositories():
        yield repositories

@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests from all repositories."""
    client = init_client()
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
    client = init_client()
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
    client = init_client()
    async for teams in client.get_teams():
        yield teams

@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflows from all repositories."""
    client = init_client()
    async for repositories in client.get_repositories():
        tasks = []
        for repo in repositories:
            async for workflows in client.get_workflows(repo["name"]):
                # Enrich workflow data with repository information
                for workflow in workflows:
                    workflow["repository"] = repo
                    runs = await client.get_workflow_runs(repo["name"], workflow["id"], per_page=1)
                    workflow["latest_run"] = runs[0] if runs else {"status": "unknown"}
                tasks.append(workflows)
        
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

@ocean.on_webhook()
async def on_webhook(webhook_data: dict) -> None:
    """Handle webhook events from GitHub."""
    event_type = webhook_data.get("event")
    if not event_type:
        return

    # Map GitHub webhook events to resource kinds
    event_mapping = {
        ObjectKind.REPOSITORY: ["created", "deleted", "archived", "unarchived", "edited", "renamed", "transferred"],
        ObjectKind.PULL_REQUEST: ["opened", "closed", "reopened", "edited", "merged"],
        ObjectKind.ISSUE: ["opened", "closed", "reopened", "edited", "deleted"],
        ObjectKind.TEAM: ["created", "deleted", "edited"],
        ObjectKind.WORKFLOW: ["workflow_run"]
    }

    # Find the relevant resource kind for this event
    for kind, events in event_mapping.items():
        if event_type in events:
            logger.info(f"Processing webhook event {event_type} for kind {kind}")
            config = cast(ResourceConfig, event.resource_config)
            await ocean.register_raw_resync([config])
            break
