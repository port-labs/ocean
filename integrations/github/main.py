from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from github.clients.client_factory import create_github_client
from github.clients.utils import integration_config
from github.helpers.utils import ObjectKind
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_client import GithubWebhookClient
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.options import ListRepositoryOptions
from utils import validate_passed_config


@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration and set up webhooks."""
    logger.info("Starting Port Ocean GitHub integration")

    validate_passed_config()

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    client: GithubWebhookClient = cast(
        GithubWebhookClient,
        await create_github_client(
            GithubClientType.WEBHOOK,
            webhook_secret=ocean.integration_config["webhook_secret"],
        ),
    )

    logger.info("Subscribing to GitHub webhooks")
    await client.upsert_webhook(base_url, WEBHOOK_CREATE_EVENTS)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    client = await create_github_client()
    exporter_factory = ExporterFactory()
    exporter = exporter_factory.get_exporter(ObjectKind(kind))(client)

    port_app_config = cast("GithubPortAppConfig", event.port_app_config)
    options = ListRepositoryOptions(type=port_app_config.repository_visibility_filter)

    async for repositories in exporter.get_paginated_resources(options):
        yield repositories


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
