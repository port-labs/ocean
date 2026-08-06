# integrations/github/main.py
import asyncio
from datetime import datetime, timedelta
from typing import cast, List, Dict, Any

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent, WebhookEventRawResults, EventPayload, EventHeaders
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from github.client import GitHubClient
from initialize_client import create_github_client
from integration import (
    PullRequestResourceConfig,
    IssueResourceConfig,
    FileResourceConfig,
    FolderResourceConfig,
)

from webhook_processors.pull_request import PullRequestWebhookProcessor
from webhook_processors.issue import IssueWebhookProcessor
from webhook_processors.file import FileWebhookProcessor
from webhook_processors.folder import FolderWebhookProcessor

from utils import ObjectKind

@ocean.on_start()
async def on_start() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        return
    client = create_github_client()
    await client.create_webhooks(base_url)
    logger.info("GitHub integration started and webhooks configured.")

@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    # Optional: Implement ETag caching if needed
    async for batch in client.get_repositories():
        logger.info(f"Resynced {len(batch)} repositories")
        yield batch

@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    selector = cast(PullRequestResourceConfig, event.resource_config).selector
    since = (datetime.utcnow() - timedelta(days=selector.days_back)).isoformat() + "Z"
    # Fetch repos first
    repo_tasks = []
    async for repo_batch in client.get_repositories():
        for repo in repo_batch:
            repo_tasks.append(client.get_pull_requests(repo["full_name"], selector.statuses, since))
    async for pr_batch in stream_async_iterators_tasks(*repo_tasks):
        if pr_batch:
            logger.info(f"Resynced {len(pr_batch)} pull requests")
            yield pr_batch

@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    selector = cast(IssueResourceConfig, event.resource_config).selector
    since = (datetime.utcnow() - timedelta(days=selector.days_back)).isoformat() + "Z"
    repo_tasks = []
    async for repo_batch in client.get_repositories():
        for repo in repo_batch:
            repo_tasks.append(client.get_issues(repo["full_name"], selector.statuses, since))
    async for issue_batch in stream_async_iterators_tasks(*repo_tasks):
        if issue_batch:
            logger.info(f"Resynced {len(issue_batch)} issues")
            yield issue_batch

@ocean.on_resync(ObjectKind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    selector = cast(FileResourceConfig, event.resource_config).selector
    repo_tasks = []
    async for repo_batch in client.get_repositories():
        for repo in repo_batch:
            repo_tasks.append(client.get_files(
                repo["full_name"], repo["id"], repo["default_branch"],
                selector.extensions, selector.paths
            ))
    async for file_batch in stream_async_iterators_tasks(*repo_tasks):
        if file_batch:
            logger.info(f"Resynced {len(file_batch)} files")
            yield file_batch

@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    selector = cast(FolderResourceConfig, event.resource_config).selector
    async for repo_batch in client.get_repositories():
        for repo in repo_batch:
            async for folder_batch in client.get_folders(
                repo["full_name"], repo["id"], repo["default_branch"], selector.paths
            ):
                if folder_batch:
                    logger.info(f"Resynced {len(folder_batch)} folders from {repo['full_name']}")
                    yield folder_batch
    client = create_github_client()
    selector = cast(FolderResourceConfig, event.resource_config).selector
    repo_tasks = []
    async for repo_batch in client.get_repositories():
        for repo in repo_batch:
            # Mock get_folders as async for consistency
            folders = await asyncio.to_thread(client.get_folders, repo["full_name"], repo["default_branch"], selector.paths)
            for folder in folders:
                folder["repository_id"] = repo["id"]
            if folders:
                yield folders

# Register webhook processors
ocean.add_webhook_processor("/integration/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/integration/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/integration/webhook", FileWebhookProcessor)
ocean.add_webhook_processor("/integration/webhook", FolderWebhookProcessor)