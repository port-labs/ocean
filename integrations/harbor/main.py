"""Harbor integration main module."""

import asyncio
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
from harbor.webhook.webhook_client import HarborWebhookClient
from harbor.core.options import (
    ListProjectOptions,
    ListUserOptions,
    ListRepositoryOptions,
    ListArtifactOptions,
)
from harbor.helpers.utils import ObjectKind
from harbor.webhook.registry import register_harbor_webhooks
from integration import (
    HarborProjectsConfig,
    HarborUsersConfig,
    HarborRepositoriesConfig,
    HarborArtifactsConfig,
)
from harbor.webhook.events import WEBHOOK_CREATE_EVENTS


@ocean.on_resync(ObjectKind.PROJECTS)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor projects."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    exporter = HarborProjectExporter(client)
    config = cast(HarborProjectsConfig, event.resource_config)

    options = ListProjectOptions(
        q=config.selector.q,
        sort=config.selector.sort,
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
        q=config.selector.q,
        sort=config.selector.sort,
    )

    async for users in exporter.get_paginated_resources(options):
        yield users


@ocean.on_resync(ObjectKind.REPOSITORIES)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    project_exporter = HarborProjectExporter(client)
    repository_exporter = HarborRepositoryExporter(client)
    config = cast(HarborRepositoriesConfig, event.resource_config)

    project_options = ListProjectOptions()
    selector = getattr(config, "selector", {})

    async for projects in project_exporter.get_paginated_resources(project_options):
        for project in projects:
            async for repositories in repository_exporter.get_paginated_resources(
                ListRepositoryOptions(
                    project_name=project["name"],
                    q=getattr(selector, "q", None),
                    sort=getattr(selector, "sort", None),
                )
            ):
                yield repositories


@ocean.on_resync(ObjectKind.ARTIFACTS)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Harbor artifacts by fetching all repositories first."""
    logger.info(f"Starting resync for kind: {kind}")

    client = init_client()
    project_exporter = HarborProjectExporter(client)
    repository_exporter = HarborRepositoryExporter(client)
    artifact_exporter = HarborArtifactExporter(client)
    config = cast(HarborArtifactsConfig, event.resource_config)

    project_options = ListProjectOptions()
    selector = getattr(config, "selector", {})

    async for projects in project_exporter.get_paginated_resources(project_options):
        for project in projects:
            async for repositories in repository_exporter.get_paginated_resources(
                ListRepositoryOptions(
                    project_name=project["name"],
                    q=getattr(selector, "q", None),
                    sort=getattr(selector, "sort", None),
                )
            ):
                tasks = [
                    artifact_exporter.get_paginated_resources(
                        ListArtifactOptions(
                            project_name=repository.get("project_name"),
                            repository_name=repository["name"],
                            q=getattr(selector, "q", None),
                            sort=getattr(selector, "sort", None),
                            with_tag=getattr(selector, "with_tag", None),
                            with_label=getattr(selector, "with_label", None),
                            with_scan_overview=getattr(
                                selector, "with_scan_overview", None
                            ),
                            with_sbom_overview=getattr(
                                selector, "with_sbom_overview", None
                            ),
                            with_signature=getattr(selector, "with_signature", None),
                            with_immutable_status=getattr(
                                selector, "with_immutable_status", None
                            ),
                            with_accessory=getattr(selector, "with_accessory", None),
                        )
                    )
                    for repository in repositories
                ]

                async for artifacts in stream_async_iterators_tasks(*tasks):
                    yield artifacts


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Harbor integration."""
    logger.info("Starting Harbor integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url

    if not base_url:
        return

    client = init_client()
    project_exporter = HarborProjectExporter(client)
    project_options = ListProjectOptions()

    webhook_secret = ocean.integration_config.get("webhook_secret")
    webhook_client = HarborWebhookClient(client, webhook_secret)

    logger.info("Creating Harbor webhooks for all projects")

    async for projects_page in project_exporter.get_paginated_resources(
        project_options
    ):
        tasks = [
            webhook_client.upsert_webhook(
                base_url, project["name"], WEBHOOK_CREATE_EVENTS
            )
            for project in projects_page
        ]

        await asyncio.gather(*tasks)
        logger.info("Successfully upserted Harbor webhooks for all projects")


register_harbor_webhooks(path="/webhook")
