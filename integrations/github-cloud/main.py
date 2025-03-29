from typing import Any, AsyncGenerator
from loguru import logger
from port_ocean.context.ocean import ocean
from initialize_client import init_client
from github_cloud.helpers.utils import ObjectKind

from github_cloud.webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from github_cloud.webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from github_cloud.webhook_processors.pull_request_webhook_processor import PullRequestWebhookProcessor
from github_cloud.webhook_processors.team_webhook_processor import TeamWebhookProcessor
from github_cloud.webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor


@ocean.on_start()
async def on_start() -> None:
    """Handle integration start."""
    logger.info("Starting GitHub Cloud integration")
    
    client = init_client()
    
    # Call the create_webhooks_if_not_exists method
    app_host = ocean.integration_config["app_host"]
    await client.create_webhooks_if_not_exists(app_host)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repository(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync repositories."""
    try:
        client = init_client()
        async for repo in client.get_repositories():
            logger.info(f"Yielding repository: {repo['name']}")
            yield repo
    except Exception as e:
        logger.error(f"Failed to resync repository: {e}")


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync issues."""
    try:
        client = init_client()
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
        client = init_client()
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
        client = init_client()
        async for org in client.get_organizations():
            async for team in client.get_teams(org["login"]):
                logger.info(f"Yielding team: {team['name']}")
                yield team
    except Exception as e:
        logger.error(f"Failed to resync teams: {e}")


@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> AsyncGenerator[dict[Any, Any], None]:
    """Resync workflows."""
    try:
        client = init_client()
        async for repo in client.get_repositories():
            async for workflow in client.get_workflows(repo["owner"]["login"], repo["name"]):
                if "name" in workflow:
                    logger.info(f"Yielding workflow: {workflow['name']}")
                    yield workflow
                else:
                    logger.warning(f"Unexpected workflow structure: {workflow}")
    except Exception as e:
        logger.error(f"Failed to resync workflows: {e}")

    
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", TeamWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkflowWebhookProcessor)
