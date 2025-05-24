from typing import AsyncGenerator, List, Dict, Any, Optional
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from github_cloud.clients.client_factory import create_github_client
from github_cloud.helpers.utils import ObjectKind
from github_cloud.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github_cloud.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github_cloud.webhook.webhook_processors.workflow_webhook_processor import (
    WorkflowWebhookProcessor,
)
from github_cloud.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from github_cloud.webhook.webhook_factory.repository_webhook_factory import (
    RepositoryWebhookFactory,
)
from github_cloud.webhook.webhook_factory.organization_webhook_factory import (
    OrganizationWebhookFactory,
)
from github_cloud.resync_data import (
    resync_repositories,
    resync_pull_requests,
    resync_teams_with_members,
    resync_members,
    resync_workflow_runs,
    resync_workflow_jobs,
    resync_issues,
)


async def _create_webhooks(base_url: str) -> None:
    """
    Create webhooks for organizations and repositories.

    Args:
        base_url: Base URL for webhook endpoints

    Raises:
        Exception: If webhook creation fails
    """
    try:
        client = create_github_client()
        logger.info(f"Creating webhooks using base URL: {base_url}")

        # Create organization webhooks
        org_webhook_factory = OrganizationWebhookFactory(client, base_url)
        await org_webhook_factory.create_webhooks_for_organizations()

        # Create repository webhooks
        repos = []
        async for repos_batch in client.get_repositories():
            repos.extend(repos_batch)

        repo_webhook_factory = RepositoryWebhookFactory(client, base_url)
        await repo_webhook_factory.create_webhooks_for_repositories(repos)

    except Exception as e:
        logger.error(f"Failed to create webhooks: {str(e)}")
        raise


@ocean.on_start()
async def on_start() -> None:
    """
    Initialize the integration on startup.

    Creates webhooks for organizations and repositories if the event listener
    is not set to ONCE mode.

    Note:
        Webhook creation is skipped if the event listener type is ONCE.
    """
    logger.info("Starting Port Ocean GitHub Cloud Integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if base_url := ocean.app.base_url:
        await _create_webhooks(base_url)
    else:
        logger.warning("No base URL provided, skipping webhook creation")


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub repositories.

    Args:
        kind: Entity kind

    Yields:
        Batches of repositories

    Raises:
        Exception: If repository sync fails
    """
    try:
        client = create_github_client()
        async for repos_batch in resync_repositories(client):
            yield repos_batch
    except Exception as e:
        logger.error(f"Failed to sync repositories: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub pull requests.

    Args:
        kind: Entity kind

    Yields:
        Batches of pull requests

    Raises:
        Exception: If pull request sync fails
    """
    try:
        client = create_github_client()
        async for prs_batch in resync_pull_requests(client):
            yield prs_batch
    except Exception as e:
        logger.error(f"Failed to sync pull requests: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.TEAM_WITH_MEMBERS)
async def on_resync_teams_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub teams with members.

    Args:
        kind: Entity kind

    Yields:
        Batches of teams with members

    Raises:
        Exception: If team sync fails
    """
    try:
        client = create_github_client()
        async for teams_batch in resync_teams_with_members(client):
            yield teams_batch
    except Exception as e:
        logger.error(f"Failed to sync teams with members: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.MEMBER)
async def on_resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub members.

    Args:
        kind: Entity kind

    Yields:
        Batches of members

    Raises:
        Exception: If member sync fails
    """
    try:
        client = create_github_client()
        async for members_batch in resync_members(client):
            yield members_batch
    except Exception as e:
        logger.error(f"Failed to sync members: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.WORKFLOW_RUN)
async def on_resync_workflow_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub workflow runs.

    Args:
        kind: Entity kind

    Yields:
        Batches of workflow runs

    Raises:
        Exception: If workflow run sync fails
    """
    try:
        client = create_github_client()
        async for runs_batch in resync_workflow_runs(client):
            yield runs_batch
    except Exception as e:
        logger.error(f"Failed to sync workflow runs: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.WORKFLOW_JOB)
async def on_resync_workflow_jobs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub workflow jobs.

    Args:
        kind: Entity kind

    Yields:
        Batches of workflow jobs

    Raises:
        Exception: If workflow job sync fails
    """
    try:
        client = create_github_client()
        async for jobs_batch in resync_workflow_jobs(client):
            yield jobs_batch
    except Exception as e:
        logger.error(f"Failed to sync workflow jobs: {str(e)}")
        raise


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub issues.

    Args:
        kind: Entity kind

    Yields:
        Batches of issues

    Raises:
        Exception: If issue sync fails
    """
    try:
        client = create_github_client()
        async for issues_batch in resync_issues(client):
            yield issues_batch
    except Exception as e:
        logger.error(f"Failed to sync issues: {str(e)}")
        raise


@ocean.on_resync()
async def debug_handler(kind: str) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Debug handler for unknown entity kinds.

    Args:
        kind: Entity kind

    Yields:
        Empty list for unknown entity kinds
    """
    logger.info(f"Port requested sync for unknown kind: {kind}")
    yield []

ocean.add_webhook_processor("/hook/org/{org_name}", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", WorkflowWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", IssueWebhookProcessor)
