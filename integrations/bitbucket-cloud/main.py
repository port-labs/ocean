from loguru import logger
from bitbucket_integration.client import BitbucketClient
from bitbucket_integration.webhooks.handler import BitbucketWebhookHandler
from bitbucket_integration.models.main import ObjectKind
from starlette.requests import Request
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


webhook_handler = BitbucketWebhookHandler()


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Bitbucket Cloud Integration")
    await setup_application()


def get_bitbucket_client() -> BitbucketClient:
    bitbucket_username = ocean.integration_config["username"]
    bitbucket_app_password = ocean.integration_config["app_password"]
    return BitbucketClient(bitbucket_username, bitbucket_app_password)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            workspace_slug = workspace["slug"]
            async for repositories in client.fetch_repositories(workspace_slug):
                for repo in repositories:
                    yield repo


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            workspace_slug = workspace["slug"]
            async for projects in client.fetch_projects(workspace_slug):
                for project in projects:
                    yield project


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            workspace_slug = workspace["slug"]
            async for repositories in client.fetch_repositories(workspace_slug):
                for repo in repositories:
                    repo_slug = repo["slug"]
                    async for pull_requests in client.fetch_pull_requests(
                        workspace_slug, repo_slug
                    ):
                        for pr in pull_requests:
                            yield pr


@ocean.on_resync(ObjectKind.COMPONENT)
async def on_resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    async for workspaces in client.fetch_workspaces():
        for workspace in workspaces:
            workspace_slug = workspace["slug"]
            async for repositories in client.fetch_repositories(workspace_slug):
                for repo in repositories:
                    repo_slug = repo["slug"]
                    async for components in client.fetch_components(
                        workspace_slug, repo_slug
                    ):
                        for component in components:
                            yield component


async def setup_application() -> None:
    """Set up the application by registering webhooks."""
    integration_config = ocean.integration_config

    app_host = ocean.config("base_url", None)
    webhook_secret = integration_config.get("webhook_secret")

    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Bitbucket cloud"
        )
        return

    client = get_bitbucket_client()
    webhook_url = f"{app_host}/webhook"

    try:
        async for workspaces in client.fetch_workspaces():
            for workspace in workspaces:
                workspace_slug = workspace["slug"]
                try:
                    await client.register_webhook(
                        workspace_slug, webhook_url, webhook_secret
                    )
                    logger.info(
                        f"Successfully registered Bitbucket webhook for workspace: {workspace_slug}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to register Bitbucket webhook for workspace {workspace_slug}: {e}"
                    )
    except Exception as e:
        logger.error(f"Failed to fetch workspaces: {e}")


@ocean.router.post("/webhook")
async def handle_webhook(request: Request) -> dict:
    """Handle incoming webhook events from Bitbucket."""
    return await webhook_handler.handle_webhook(request)
