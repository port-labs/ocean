from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger
from fastapi import Request

from constants import ObjectKind
from client.github import GitHubClient
from webhook_handler import WebhookHandler

def get_client() -> GitHubClient:
    """Get a configured GitHub client instance."""
    return GitHubClient.from_ocean_configuration()

webhook_handler = WebhookHandler()
webhook_handler.configure_client(get_client())

# Register webhook route
@ocean.router.post("/webhook")
async def handle_webhook(request: Request) -> dict:
    """Handle incoming GitHub webhook events.
    
    This endpoint receives webhook events from GitHub when activities like
    pull request merges, issue creation, etc. occur. The events are validated
    using the webhook secret and then processed by the appropriate handlers.
    """
    return await webhook_handler.handle(request)

@ocean.on_start()
async def on_start() -> None:
    client = get_client()
    
    # Create webhook subscriptions
    try:
        webhook_secret = ocean.integration_config.get("github_webhook_secret")
        if not webhook_secret:
            logger.error("No webhook secret configured - webhooks will not work")
            return
            
        webhook_url = ocean.integration_config.get("webhook_url")
        if not webhook_url:
            logger.error("No webhook URL configured - webhooks will not work")
            return
            
        # Get all repositories and create webhooks for each
        success_count = 0
        error_count = 0
        
        async for repos in client.get_repositories():
            for repo in repos:
                try:
                    repo_name = repo.get("full_name")
                    if not repo_name:
                        continue
                        
                    await client.create_webhook(
                        repo=repo_name,
                        url=webhook_url,
                        secret=webhook_secret
                    )
                    success_count += 1
                    logger.info(f"Created webhook for repository: {repo_name}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Failed to create webhook for repository {repo.get('full_name', 'unknown')}: {e}")
                    
        if success_count > 0:
            logger.info(f"Successfully created webhooks for {success_count} repositories")
        if error_count > 0:
            logger.warning(f"Failed to create webhooks for {error_count} repositories")
            
    except Exception as e:
        logger.error(f"Failed to setup webhook subscriptions: {e}")


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for repos in client.get_repositories():
        logger.info(f"Received batch with {len(repos)} repositories")
        yield repos


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    # Get issues from all repositories
    async for repos in client.get_repositories():
        for repo in repos:
            try:
                async for issues in client.get_issues(repo["name"]):
                    logger.info(f"Received batch with {len(issues)} issues from {repo['name']}")
                    yield issues
            except Exception as e:
                logger.error(f"Failed to get issues for {repo['name']}: {e}")

@ocean.on_resync(ObjectKind.PULLREQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    # Get pull requests from all repositories
    async for repos in client.get_repositories():
        for repo in repos:
            try:
                async for pull_requests in client.get_pull_requests(repo["name"]):
                    logger.info(f"Received batch with {len(pull_requests)} pull requests from {repo['name']}")
                    yield pull_requests
            except Exception as e:
                logger.error(f"Failed to get pull requests for {repo['name']}: {e}")

@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    # Get workflows from all repositories
    async for repos in client.get_repositories():
        for repo in repos:
            try:
                async for workflows in client.get_workflows(repo["name"]):
                    logger.info(f"Received batch with {len(workflows)} workflows from {repo['name']}")
                    yield workflows
            except Exception as e:
                logger.error(f"Failed to get workflows for {repo['name']}: {e}")

@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for teams in client.get_teams():
        logger.info(f"Received batch with {len(teams)} teams")
        yield teams


