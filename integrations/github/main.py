from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from github.clients.client_factory import (
    GitHubAuthenticatorFactory,
    create_github_client,
)
from github.clients.utils import integration_config
from github.core.exporters.folder_exporter import RestFolderExporter
from github.helpers.utils import ObjectKind
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_client import GithubWebhookClient
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.options import ListFolderOptions, ListRepositoryOptions
from typing import TYPE_CHECKING
from port_ocean.context.event import event

from integration import GithubFolderResourceConfig

if TYPE_CHECKING:
    from integration import GithubPortAppConfig


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

    authenticator = GitHubAuthenticatorFactory.create(
        organization=ocean.integration_config["github_organization"],
        github_host=ocean.integration_config["github_host"],
        token=ocean.integration_config.get("github_token"),
        app_id=ocean.integration_config.get("github_app_id"),
        private_key=ocean.integration_config.get("github_app_private_key"),
    )

    client = GithubWebhookClient(
        **integration_config(authenticator),
        webhook_secret=ocean.integration_config["webhook_secret"],
    )

    logger.info("Subscribing to GitHub webhooks")
    await client.upsert_webhook(base_url, WEBHOOK_CREATE_EVENTS)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    exporter = RestRepositoryExporter(rest_client)

    port_app_config = cast("GithubPortAppConfig", event.port_app_config)
    options = ListRepositoryOptions(type=port_app_config.repository_type)

    async for repositories in exporter.get_paginated_resources(options):
        yield repositories


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all folders in specified repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    exporter = RestFolderExporter(rest_client)

    selector = cast(GithubFolderResourceConfig, event.resource_config).selector

    for folder_config in selector.folders:
        for repo in folder_config.repos:
            base_path = folder_config.path if folder_config.path != "*" else None
            options = ListFolderOptions(repo=repo, path=base_path)
            async for folder_batch in exporter.get_paginated_resources(options):
                yield folder_batch


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
