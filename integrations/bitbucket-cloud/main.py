from loguru import logger
from bitbucket_integration.client import BitbucketClient
from webhook.utils import BitbucketWebhookHandler, ObjectKind
from starlette.requests import Request
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

webhook_handler = BitbucketWebhookHandler()

@ocean.on_start()
async def on_start() -> None:
    """Initialize the Bitbucket Cloud integration when the application starts."""
    logger.info("Starting Port Ocean Bitbucket Cloud Integration")
    await setup_application()

def get_bitbucket_client() -> BitbucketClient:
    """Retrieve a Bitbucket client instance using stored integration credentials."""
    config = ocean.integration_config
    return BitbucketClient(config["username"], config["app_password"])

async def fetch_and_yield(client, fetch_function, workspace_slug=None, repo_slug=None):
    """Utility function to streamline data fetching and yielding from Bitbucket API."""
    async for items in (
        fetch_function(workspace_slug, repo_slug)
        if workspace_slug and repo_slug
        else fetch_function(workspace_slug)
        if workspace_slug
        else fetch_function()
    ):
        for item in items:
            yield item

@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Retrieve and sync repositories from Bitbucket across available workspaces."""
    client = get_bitbucket_client()
    async for workspace in fetch_and_yield(client, client.fetch_workspaces):
        async for repo in fetch_and_yield(client, client.fetch_repositories, workspace["slug"]):
            yield repo

@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Retrieve and sync projects associated with workspaces in Bitbucket."""
    client = get_bitbucket_client()
    async for workspace in fetch_and_yield(client, client.fetch_workspaces):
        async for project in fetch_and_yield(client, client.fetch_projects, workspace["slug"]):
            yield project

@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Retrieve and sync pull requests from repositories within workspaces."""
    client = get_bitbucket_client()
    async for workspace in fetch_and_yield(client, client.fetch_workspaces):
        async for repo in fetch_and_yield(client, client.fetch_repositories, workspace["slug"]):
            async for pr in fetch_and_yield(client, client.fetch_pull_requests, workspace["slug"], repo["slug"]):
                yield pr

@ocean.on_resync(ObjectKind.COMPONENT)
async def on_resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Retrieve and sync repository components from Bitbucket."""
    client = get_bitbucket_client()
    async for workspace in fetch_and_yield(client, client.fetch_workspaces):
        async for repo in fetch_and_yield(client, client.fetch_repositories, workspace["slug"]):
            async for component in fetch_and_yield(client, client.fetch_components, workspace["slug"], repo["slug"]):
                yield component

async def setup_application() -> None:
    """Set up webhooks for Bitbucket workspaces to receive real-time updates."""
    integration_config = ocean.integration_config
    app_host, webhook_secret = integration_config.get("base_url", None), integration_config.get("webhook_secret")

    if not app_host or not webhook_secret:
        logger.error("Missing required configuration: app_host or webhook_secret. Webhooks will not be set up.")
        return

    client = get_bitbucket_client()
    webhook_url = f"{app_host}/webhook"

    try:
        async for workspace in fetch_and_yield(client, client.fetch_workspaces):
            try:
                await client.register_webhook(workspace["slug"], webhook_url, webhook_secret)
                logger.info(f"Successfully registered Bitbucket webhook for workspace: {workspace['slug']}")
            except Exception as e:
                logger.error(f"Failed to register Bitbucket webhook for workspace {workspace['slug']}: {e}")
    except Exception as e:
        logger.error(f"Failed to fetch workspaces: {e}")

@ocean.router.post("/webhook")
async def handle_webhook(request: Request) -> dict:
    """Process incoming webhook events from Bitbucket and delegate handling."""
    return await webhook_handler.handle_webhook(request)
