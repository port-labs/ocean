"""Harbor integration main module."""

from typing import cast
from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from initialize_client import init_client
from harbor.core.exporters.project_exporter import HarborProjectExporter
from harbor.core.exporters.user_exporter import HarborUserExporter
from harbor.core.exporters.repository_exporter import HarborRepositoryExporter
from harbor.core.exporters.artifact_exporter import HarborArtifactExporter
from harbor.core.options import (
    ListProjectOptions,
    ListUserOptions,
    ListRepositoryOptions,
    ListArtifactOptions,
)
from harbor.helpers.utils import ObjectKind
from harbor.webhook.webhook_client import log_harbor_webhook_config
from harbor.webhook.events import WEBHOOK_CREATE_EVENTS
from harbor.webhook.registry import register_harbor_webhooks
from integration import (
    HarborProjectsConfig,
    HarborUsersConfig,
    HarborRepositoriesConfig,
    HarborArtifactsConfig,
)


@ocean.on_resync(ObjectKind.PROJECTS)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor projects."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    exporter = HarborProjectExporter(client)
    config = cast(HarborProjectsConfig, event.resource_config)

    options = ListProjectOptions(
        name_prefix=config.selector.name_prefix,
        visibility=config.selector.visibility,
        owner=config.selector.owner,
    )

    async for projects in exporter.get_paginated_resources(options):
        yield projects


@ocean.on_resync(ObjectKind.USERS)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor users."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    exporter = HarborUserExporter(client)
    config = cast(HarborUsersConfig, event.resource_config)

    options = ListUserOptions(
        username_prefix=config.selector.username_prefix,
        email=config.selector.email,
        admin_only=config.selector.admin_only,
    )

    async for users in exporter.get_paginated_resources(options):
        yield users


@ocean.on_resync(ObjectKind.REPOSITORIES)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    exporter = HarborRepositoryExporter(client)
    config = cast(HarborRepositoriesConfig, event.resource_config)

    options = ListRepositoryOptions(
        project_name=config.selector.project_name,
        repository_name=config.selector.repository_name,
        label=config.selector.label,
        q=config.selector.q,
    )

    async for repositories in exporter.get_paginated_resources(options):
        yield repositories


@ocean.on_resync(ObjectKind.ARTIFACTS)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor artifacts by fetching all repositories first."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    repository_exporter = HarborRepositoryExporter(client)
    artifact_exporter = HarborArtifactExporter(client)
    config = cast(HarborArtifactsConfig, event.resource_config)

    # Get all repositories first (already enriched with project_name)
    repository_options = ListRepositoryOptions()

    # Apply filtering from the config selector
    selector = getattr(config, "selector", {})

    all_repositories = []
    async for repositories in repository_exporter.get_paginated_resources(
        repository_options
    ):
        all_repositories.extend(repositories)

    # Create tasks to fetch artifacts for each repository
    tasks = []
    for repository in all_repositories:
        project_name = repository.get("project_name")
        repository_name = repository["name"]

        artifact_options = ListArtifactOptions(
            project_name=project_name,
            repository_name=repository_name,
            tag=getattr(selector, "tag", None),
            digest=getattr(selector, "digest", None),
            label=getattr(selector, "label", None),
            media_type=getattr(selector, "media_type", None),
            created_since=getattr(selector, "created_since", None),
            severity_threshold=getattr(selector, "severity_threshold", None),
            with_scan_overview=getattr(selector, "with_scan_overview", None),
            q=getattr(selector, "q", None),
        )

        tasks.append(artifact_exporter.get_paginated_resources(artifact_options))

    if tasks:
        logger.info(f"Fetching artifacts from {len(tasks)} repositories")
        async for artifacts in stream_async_iterators_tasks(*tasks):
            yield artifacts


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Harbor integration."""
    logger.info("Starting Harbor integration")

    try:
        client = init_client()
        logger.info(f"Harbor client initialized for {client.base_url}")

        # Log webhook configuration instructions
        log_harbor_webhook_config(client.base_url, WEBHOOK_CREATE_EVENTS)

    except Exception as e:
        logger.error(f"Failed to initialize Harbor client: {e}")
        raise


# Register webhook processors
register_harbor_webhooks(path="/webhook")
