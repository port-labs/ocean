from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from loguru import logger
from fastapi import Request

from constants import ObjectKind
from client.github import GitHubClient
from webhook_handler import WebhookHandler

webhook_handler = WebhookHandler()

def get_client() -> GitHubClient:
    """Get a configured GitHub client instance."""
    return GitHubClient.from_ocean_configuration()

@ocean.on_start()
async def on_start() -> None:
    # Initialize a client to verify credentials
    client = get_client()
    logger.info("GitHub client configuration verified successfully.")


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for repos in client.get_repositories(ocean.integration_config["github_org"]):
        logger.info(f"Received batch with {len(repos)} repositories")
        yield repos


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for issues in client.get_issues(ocean.integration_config["github_org"], ocean.integration_config["github_repo"]):
        logger.info(f"Received batch with {len(issues)} issues")
        yield issues

@ocean.on_resync(ObjectKind.PULLREQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for pulls in client.get_pull_requests(ocean.integration_config["github_org"], ocean.integration_config["github_repo"]):
        logger.info(f"Received batch with {len(pulls)} pull requests")
        yield pulls

@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for workflows in client.get_workflows(ocean.integration_config["github_org"], ocean.integration_config["github_repo"]):
        logger.info(f"Received batch with {len(workflows)} workflows")
        yield workflows

@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing GitHub resource: {kind}")
    client = get_client()
    
    async for teams in client.get_teams(ocean.integration_config["github_org"]):
        logger.info(f"Received batch with {len(teams)} teams")
        yield teams


@ocean.router.post("/webhook")
async def github_webhook(request: Request):
    return await webhook_handler.handle(request)

