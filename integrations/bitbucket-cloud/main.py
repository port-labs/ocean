from loguru import logger
from bitbucket_integration.client import BitbucketClient
from bitbucket_integration.webhooks.handler import BitbucketWebhookHandler
from bitbucket_integration.models.main import ObjectKind
from starlette.requests import Request
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Bitbucket Cloud Integration")
    webhook_handler = BitbucketWebhookHandler(ocean.config.base_url)
    await webhook_handler.create_webhooks()


def get_bitbucket_client() -> BitbucketClient:
    bitbucket_username = ocean.integration_config["bitbucket_username"]
    bitbucket_app_password = ocean.integration_config["bitbucket_app_password"]
    return BitbucketClient(bitbucket_username, bitbucket_app_password)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            async for repositories in client.fetch_repositories(workspace["slug"]):
                yield repositories


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            async for projects in client.fetch_projects(workspace["slug"]):
                yield projects


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            async for repositories in client.fetch_repositories(workspace["slug"]):
                for repo in repositories:
                    async for pull_requests in client.fetch_pull_requests(
                        workspace["slug"], repo["slug"]
                    ):
                        yield pull_requests


@ocean.on_resync(ObjectKind.COMPONENT)
async def on_resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            async for repositories in client.fetch_repositories(workspace["slug"]):
                for repo in repositories:
                    async for components in client.fetch_components(
                        workspace["slug"], repo["slug"]
                    ):
                        yield components


@ocean.router.post("/webhook")
async def handle_webhook(request: Request) -> dict:
    """Handle incoming webhook events from Bitbucket."""
    webhook_handler = BitbucketWebhookHandler()
    return await webhook_handler.handle_webhook(request)
