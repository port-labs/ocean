"""
main.py
-------
Main entry point for the GitHub integration.
Registers on_resync handlers and webhook processors with Ocean and starts the integration via ocean.sail().
"""

from typing import Any, AsyncGenerator

from loguru import logger

from port_ocean.context.ocean import ocean

# Import helper to create a GitHub client from integration configuration.
from initialize_client import create_github_client

# Import the kinds enum
from kinds import Kinds
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

# --- Register Webhook Processors ---
from webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowRunWebhookProcessor
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor


# --- On-Resync Handlers ---
@ocean.on_resync(Kinds.REPOSITORY)
async def on_resync_repositories(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    async for repo in client.fetch_resource("org_repos", org=client.org):
        yield repo


@ocean.on_resync(Kinds.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    """
    1. Retrieve all org repos (org_repos).
    2. For each repo, retrieve pull_requests => '/repos/{owner}/{repo}/pulls'
    3. Yield each PR.
    """
    client = create_github_client()
    org = client.org

    # 1) Get all repositories in the org
    async for repo in client.fetch_resource("org_repos", org=org):
        repo_name = repo.get("name")
        if not repo_name:
            continue

        # 2) For each repo, fetch the pull requests
        async for pr in client.fetch_resource("pull_requests", owner=org, repo=repo_name):
            yield pr


@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    """
    Similar pattern: retrieve org repos, then for each, call fetch_resource("issues") => /repos/{owner}/{repo}/issues
    Exclude any that contain 'pull_request' from the issues list (which are actually PRs).
    """
    client = create_github_client()
    org = client.org

    async for repo in client.fetch_resource("org_repos", org=org):
        repo_name = repo.get("name")
        if not repo_name:
            continue

        async for issue in client.fetch_resource("issues", owner=org, repo=repo_name):
            if "pull_request" in issue:
                continue
            yield issue


@ocean.on_resync(Kinds.TEAM)
async def on_resync_teams(kind: str) -> AsyncGenerator[dict[str, Any], None]:
    client = create_github_client()
    org = client.org

    async for team in client.fetch_resource("teamsFull", org=org):
        yield team


@ocean.on_resync(Kinds.WORKFLOW)
async def on_resync_workflows(kind:str) -> AsyncGenerator[dict[str, Any], None]:
    """
    For each repo, calls 'workflows' => '/repos/{owner}/{repo}/actions/workflows'
    which typically returns a dict with a 'workflows' list.
    So your fetch_resource logic will store it as a single dict.
    We'll handle that carefully.
    """
    client = create_github_client()
    org = client.org

    async for repo in  client.fetch_resource("org_repos", org=org):
        repo_name = repo.get("name")
        if not repo_name:
            continue

        async for workflow in client.fetch_resource("workflows", owner=org, repo=repo_name):
            yield workflow






# --- On Start Handler ---
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitHub integration")
    # Optionally: Initialize webhooks on GitHub if required,
    # e.g., call client.create_webhooks() with your app host.




# --- Optional Health Endpoint ---
@ocean.router.get("/health")
def health():
    return {"status": "ok"}


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", TeamWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkflowRunWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)