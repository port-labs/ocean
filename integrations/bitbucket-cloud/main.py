from loguru import logger
from starlette.requests import Request
from bitbucket_integration.client import BitbucketClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from bitbucket_integration.webhooks.event_process import process_repo_push_event, process_pull_request_event
from bitbucket_integration.utils import validate_webhook_payload
from enum import StrEnum

class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PROJECT = "project"
    PULL_REQUEST = "pull-request"
    COMPONENT = "component"


@ocean.on_start()
async def on_start() -> None:
    """Register a webhook with Bitbucket when the application starts."""
    integration_config = ocean.integration_config
    logger.info("Starting Bitbucket Cloud ntegration")

    app_host = integration_config.get("app_host", None)

    client = get_bitbucket_client()
    webhook_url = f"{app_host}/webhook"
    webhook_secret = integration_config.get("webhook_secret")

    try:
        await client.register_webhook(webhook_url, webhook_secret)
        logger.info("Successfully registered Bitbucket webhook")
    except Exception as e:
        logger.error(f"Failed to register Bitbucket webhook: {e}")


# Initialize Bitbucket cloud client
def get_bitbucket_client() -> BitbucketClient:
    bitbucket_token = ocean.integration_config["bitbucket_token"]
    bitbucket_workspace = ocean.integration_config["bitbucket_workspace"]
    return BitbucketClient(bitbucket_workspace, bitbucket_token)

# Resync handler for repositories
@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    repositories = await client.fetch_repositories()
    for repo in repositories:
        yield repo

# Resync handler for projects
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    projects = await client.fetch_projects()
    for project in projects:
        yield project

# Resync handler for pull requests
@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    repositories = await client.fetch_repositories()
    for repo in repositories:
        repo_slug = repo["slug"]
        pull_requests = await client.fetch_pull_requests(repo_slug)
        for pr in pull_requests:
            yield pr

# Resync handler for components
@ocean.on_resync(ObjectKind.COMPONENT)
async def on_resync_components(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_bitbucket_client()
    repositories = await client.fetch_repositories()
    for repo in repositories:
        repo_slug = repo["slug"]
        components = await client.fetch_components(repo_slug)
        for component in components:
            yield component

@ocean.router.post("/webhook")
async def handle_webhook(request: Request) -> dict:
    """Handle incoming webhook events from Bitbucket."""
    secret = ocean.integration_config.get("webhook_secret")
    if not await validate_webhook_payload(request, secret):
        return {"ok": False, "error": "Unauthorized"}

    event = await request.json()
    event_type = request.headers.get("X-Event-Key")
    logger.info(f"Received Bitbucket webhook event: {event_type}")

    try:
        if event_type == "repo:push":
            await process_repo_push_event(event)
        elif event_type == "pullrequest:created":
            await process_pull_request_event(event)

        return {"ok": True}
    except Exception as e:
        logger.error(f"Failed to handle webhook event: {e}")
        return {"ok": False, "error": str(e)}

