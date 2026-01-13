"""Main entry point for Harbor integration."""

from typing import cast

from loguru import logger

from harbor.clients.client_factory import HarborClientFactory
from harbor.core.exporters.project_exporter import HarborProjectExporter
from harbor.core.exporters.repository_exporter import HarborRepositoryExporter
from harbor.core.exporters.artifact_exporter import HarborArtifactExporter
from harbor.core.exporters.user_exporter import HarborUserExporter
from harbor.core.options import ListArtifactOptions, ListProjectOptions
from integration import (
    ArtifactResourceConfig,
    ProjectResourceConfig,
)
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook_processors.artifact_webhook_processor import ArtifactWebhookProcessor


@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor projects from the API.
    """
    client = HarborClientFactory.get_client()
    project_exporter = HarborProjectExporter(client)

    resource_config = cast(ProjectResourceConfig, event.resource_config)
    selector = resource_config.selector

    options: ListProjectOptions = {}
    public = getattr(selector, "public", None)
    if public is not None:
        options["public"] = public

    logger.info(f"Starting resync for Harbor projects with options: {options}")

    async for projects in project_exporter.get_paginated_resources(options):
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(Kinds.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor repositories from the API.
    """
    client = HarborClientFactory.get_client()
    repository_exporter = HarborRepositoryExporter(client)

    logger.info("Starting resync for Harbor repositories")

    async for repositories in repository_exporter.get_paginated_resources():
        logger.info(f"Received repository batch with {len(repositories)} repositories")
        yield repositories


@ocean.on_resync(Kinds.ARTIFACT)
async def on_resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor artifacts from the API.
    """
    client = HarborClientFactory.get_client()
    artifact_exporter = HarborArtifactExporter(client)

    resource_config = cast(ArtifactResourceConfig, event.resource_config)
    selector = resource_config.selector

    options: ListArtifactOptions = {}
    tag = getattr(selector, "tag", None)
    digest = getattr(selector, "digest", None)
    label = getattr(selector, "label", None)
    media_type = getattr(selector, "media_type", None)
    created_since = getattr(selector, "created_since", None)

    if tag:
        options["tag"] = tag
    if digest:
        options["digest"] = digest
    if label:
        options["label"] = label
    if media_type:
        options["media_type"] = media_type
    if created_since:
        options["created_since"] = created_since

    logger.info(f"Starting resync for Harbor artifacts with options: {options}")

    async for artifacts in artifact_exporter.get_paginated_resources(options):
        yield artifacts


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor users from the API.
    """
    client = HarborClientFactory.get_client()
    user_exporter = HarborUserExporter(client)

    logger.info("Starting resync for Harbor users")

    async for users in user_exporter.get_paginated_resources():
        logger.info(f"Received user batch with {len(users)} users")
        yield users


@ocean.on_start()
async def on_start() -> None:
    """Called once when the integration starts."""
    logger.info("Starting Harbor integration")


# Register webhook processors for real-time event handling
ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
