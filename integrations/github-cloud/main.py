from typing import Any, AsyncGenerator
from loguru import logger
from port_ocean.context.ocean import ocean
from github_cloud.initialize_client import init_client
from github_cloud.helpers.utils import ObjectKind
from github_cloud.webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from github_cloud.webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from github_cloud.webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor
from github_cloud.webhook_processors.team_webhook_processor import TeamWebhookProcessor
from github_cloud.webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor
from github_cloud.client import GitHubClient, WebhookConfig, WebhookManager
from github_cloud.models.webhook import WebhookEvent


async def get_client() -> GitHubClient:
    """Get initialized GitHub client."""
    return init_client()


@ocean.on_start()
async def on_start() -> None:
    """Handle integration start."""
    logger.info("Starting GitHub Cloud integration")
    
    client = await get_client()
    
    # Set up webhooks if secret is provided
    if "webhook_secret" in ocean.integration_config:
        webhook_config = WebhookConfig(
            url=f"{ocean.app.base_url}/integration/webhook",
            secret=ocean.integration_config["webhook_secret"],
            events=[
                WebhookEvent.PUSH,
                WebhookEvent.PULL_REQUEST,
                WebhookEvent.ISSUES,
                WebhookEvent.WORKFLOW_RUN
            ]
        )
        webhook_manager = WebhookManager(client, webhook_config)
        
        # Set up webhooks for all repositories
        async for repo in client.get_repositories():
            owner = repo["owner"]["login"]
            repo_name = repo["name"]
            await webhook_manager.sync_repository_webhooks(owner, repo_name)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repository(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync repositories."""
    try:
        client = await get_client()
        async for repo in client.get_repositories():
            logger.info(f"Yielding repository: {repo['name']}")
            yield repo
    except Exception as e:
        logger.error(f"Failed to resync repository: {e}")


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync issues."""
    try:
        client = await get_client()
        async for repo in client.get_repositories():
            async for issue in client.get_issues(repo["owner"]["login"], repo["name"]):
                logger.info(f"Yielding issue: {issue['title']}")
                yield issue
    except Exception as e:
        logger.error(f"Failed to resync issues: {e}")


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync pull requests."""
    try:
        client = await get_client()
        async for repo in client.get_repositories():
            async for pull_request in client.get_pull_requests(repo["owner"]["login"], repo["name"]):
                logger.info(f"Yielding pull request: {pull_request['title']}")
                yield pull_request
    except Exception as e:
        logger.error(f"Failed to resync pull requests: {e}")


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync teams."""
    try:
        client = await get_client()
        async for team in client.get_teams():
            logger.info(f"Yielding team: {team['name']}")
            yield team
    except Exception as e:
        logger.error(f"Failed to resync teams: {e}")


@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync workflows."""
    try:
        client = await get_client()
        async for repo in client.get_repositories():
            async for workflow in client.get_workflows(repo["owner"]["login"], repo["name"]):
                if "name" in workflow:
                    logger.info(f"Yielding workflow: {workflow['name']}")
                    yield workflow
                else:
                    logger.warning(f"Unexpected workflow structure: {workflow}")
    except Exception as e:
        logger.error(f"Failed to resync workflows: {e}")


# Register webhook processors
webhook_processors = [
    RepositoryWebhookProcessor,
    IssueWebhookProcessor,
    PullRequestWebhookProcessor,
    TeamWebhookProcessor,
    WorkflowWebhookProcessor
]

for processor in webhook_processors:
    ocean.add_webhook_processor("/webhook", processor)
