"""Harbor integration main module."""

import asyncio
from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from harbor.clients.client_factory import HarborClientFactory
from harbor.core.exporters.artifact_exporter import HarborArtifactExporter
from harbor.core.exporters.project_exporter import HarborProjectExporter
from harbor.core.exporters.repository_exporter import HarborRepositoryExporter
from harbor.core.exporters.user_exporter import HarborUserExporter
from harbor.core.options import (
    ListArtifactOptions,
    ListProjectOptions,
    ListRepositoryOptions,
    ListUserOptions,
)
from harbor.helpers.utils import ObjectKind
from harbor.webhooks.events import WEBHOOK_EVENTS_TO_LISTEN
from harbor.webhooks.processors.artifact_webhook_processor import (
    ArtifactWebhookProcessor,
)
from harbor.webhooks.processors.project_webhook_processor import (
    ProjectWebhookProcessor,
)
from harbor.webhooks.processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from harbor.webhooks.webhook_client import HarborWebhookClient
from integration import (
    HarborArtifactConfig,
    HarborProjectConfig,
    HarborRepositoryConfig,
    HarborUserConfig,
)


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Harbor integration."""
    logger.info("Starting Harbor Ocean integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        logger.warning("No base_url configured, skipping webhook setup")
        return

    webhook_secret = ocean.integration_config.get("webhook_secret")
    if not webhook_secret:
        logger.warning("No webhook secret configured, skipping webhook setup")
        return

    client = HarborClientFactory.get_client()
    project_exporter = HarborProjectExporter(client)

    webhook_client = HarborWebhookClient(client, webhook_secret)

    logger.info("Creating Harbor webhooks for all projects")

    project_options: ListProjectOptions = {}
    webhook_url = f"{base_url}/webhook"

    async for projects in project_exporter.get_paginated_resources(project_options):
        tasks = [
            webhook_client.upsert_webhook(
                project["name"],
                webhook_url,
                WEBHOOK_EVENTS_TO_LISTEN,
            )
            for project in projects
        ]

        await asyncio.gather(*tasks)

    logger.info("Successfully set up Harbor webhooks for all projects")


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor projects.

    Args:
        kind: Resource kind being resynced

    Yields:
        Batches of projects
    """
    logger.info(f"Starting resync for kind: {kind}")

    client = HarborClientFactory.get_client()
    exporter = HarborProjectExporter(client)
    config = cast(HarborProjectConfig, event.resource_config)

    options: ListProjectOptions = {
        "q": config.selector.q,
        "sort": config.selector.sort,
    }

    async for projects in exporter.get_paginated_resources(options):
        yield projects


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor users.

    Args:
        kind: Resource kind being resynced

    Yields:
        Batches of users
    """
    logger.info(f"Starting resync for kind: {kind}")

    client = HarborClientFactory.get_client()
    exporter = HarborUserExporter(client)
    config = cast(HarborUserConfig, event.resource_config)

    options: ListUserOptions = {
        "q": config.selector.q,
        "sort": config.selector.sort,
    }

    async for users in exporter.get_paginated_resources(options):
        yield users


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor repositories.

    Args:
        kind: Resource kind being resynced

    Yields:
        Batches of repositories
    """
    logger.info(f"Starting resync for kind: {kind}")

    client = HarborClientFactory.get_client()
    project_exporter = HarborProjectExporter(client)
    repository_exporter = HarborRepositoryExporter(client)
    config = cast(HarborRepositoryConfig, event.resource_config)

    project_options: ListProjectOptions = {}

    async for projects in project_exporter.get_paginated_resources(project_options):
        for project in projects:
            repository_options: ListRepositoryOptions = {
                "project_name": project["name"],
                "q": config.selector.q,
                "sort": config.selector.sort,
            }

            async for repositories in repository_exporter.get_paginated_resources(repository_options):
                yield repositories


@ocean.on_resync(ObjectKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor artifacts.

    Args:
        kind: Resource kind being resynced

    Yields:
        Batches of artifacts
    """
    logger.info(f"Starting resync for kind: {kind}")

    client = HarborClientFactory.get_client()
    project_exporter = HarborProjectExporter(client)
    repository_exporter = HarborRepositoryExporter(client)
    artifact_exporter = HarborArtifactExporter(client)
    config = cast(HarborArtifactConfig, event.resource_config)

    project_options: ListProjectOptions = {}

    async for projects in project_exporter.get_paginated_resources(project_options):
        for project in projects:
            repository_options: ListRepositoryOptions = {
                "project_name": project["name"],
            }

            async for repositories in repository_exporter.get_paginated_resources(repository_options):
                for repository in repositories:
                    artifact_options: ListArtifactOptions = {
                        "project_name": project["name"],
                        "repository_name": repository["name"],
                        "q": config.selector.q,
                        "sort": config.selector.sort,
                        "with_tag": config.selector.with_tag,
                        "with_label": config.selector.with_label,
                        "with_scan_overview": config.selector.with_scan_overview,
                        "with_sbom_overview": config.selector.with_sbom_overview,
                        "with_signature": config.selector.with_signature,
                        "with_immutable_status": config.selector.with_immutable_status,
                        "with_accessory": config.selector.with_accessory,
                    }

                    async for artifacts in artifact_exporter.get_paginated_resources(artifact_options):
                        yield artifacts


# sets-up this integration webhooks to a default `webhooks` URL path
ocean.add_webhook_processor('/webhook', ArtifactWebhookProcessor)
ocean.add_webhook_processor('/webhook', ProjectWebhookProcessor)
ocean.add_webhook_processor('/webhook', RepositoryWebhookProcessor)
