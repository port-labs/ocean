"""
main.py
-------
Main entry point for the GitHub integration.
Registers on_resync handlers and webhook processors with Ocean and starts the integration via ocean.sail().
"""

import os
import typing
from typing import Any, AsyncGenerator

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

# Import helper to create a GitHub client from integration configuration.
from initialize_client import create_github_client

# Import the kinds enum
from kinds import Kinds

# --- Register Webhook Processors ---
from webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowRunWebhookProcessor
from webhook_processors.push_webhook_processor import PushWebhookProcessor
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor

# --- Setup application ---
async def setup_application() -> None:
    base_url = ocean.integration_config["base_url"]#ocean.app.base_url ##'https://e459-102-89-41-50.ngrok-free.app'
    if not base_url:
        return

    client = create_github_client()
    await client.create_webhooks(base_url)


# --- On-Resync Handlers ---
@ocean.on_resync(Kinds.REPOSITORY)
async def on_resync_repositories(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for repo in client.fetch_repositories():
        yield {"kind": Kinds.REPOSITORY, "raw": repo}

@ocean.on_resync(Kinds.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for repo in client.fetch_repositories():
        repo_name = repo.get("name")
        async for pr in client.fetch_pull_requests(repo_name):
            yield {"kind": Kinds.PULL_REQUEST, "raw": pr}

@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for repo in client.fetch_repositories():
        repo_name = repo.get("name")
        async for issue in client.fetch_issues(repo_name):
            # Exclude pull requests (GH returns them in the issues endpoint too)
            if "pull_request" in issue:
                continue
            yield {"kind": Kinds.ISSUE, "raw": issue}

@ocean.on_resync(Kinds.TEAM)
async def on_resync_teams(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for team in client.fetch_teams():
        yield {"kind": Kinds.TEAM, "raw": team}

@ocean.on_resync(Kinds.WORKFLOW)
async def on_resync_workflows(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for repo in client.fetch_repositories():
        repo_name = repo.get("name")
        async for workflow in client.fetch_workflows(repo_name):
            yield {"kind": Kinds.WORKFLOW, "raw": workflow}

@ocean.on_resync(Kinds.FILE)
async def on_resync_files(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for repo in client.fetch_repositories():
        repo_name = repo.get("name")
        async for content in client.fetch_files(repo_name):
            yield {"kind": Kinds.FILE, "raw": content}

# --- On Start Handler ---
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitHub integration")
    # Optionally: Initialize webhooks on GitHub if required,
    # e.g., call client.create_webhooks() with your app host.
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()




# --- Optional Health Endpoint ---
@ocean.router.get("/health")
def health():
    return {"status": "ok"}


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", TeamWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkflowRunWebhookProcessor)
ocean.add_webhook_processor("/webhook", PushWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)