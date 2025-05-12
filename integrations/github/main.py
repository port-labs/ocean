import typing
from loguru import logger
from integration import GithubRepositoryConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from github.clients.client_factory import create_github_client
from github.utils import ObjectKind
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)


@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration and set up webhooks."""
    logger.info("Starting Port Ocean GitHub integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    client = create_github_client()
    webhook_events = [
        "repository",
        "pull_request",
        "issues",
        "team",
        "workflow_run",
        "deployment",
        "dependabot_alert",
        "push",
        "code_scanning_alert",
        "release",
        "create",
    ]
    logger.info("Subscribing to GitHub webhooks")
    await client.create_or_update_webhook(base_url, webhook_events)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_github_client()

    config = typing.cast(GithubRepositoryConfig, event.resource_config)
    params = {"type": config.selector.type}

    async for repositories in client.get_repositories(params):
        yield repositories


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
