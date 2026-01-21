from typing import Any, cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook_processors.artifact_webhook_processor import ArtifactWebhookProcessor

from initialize_client import create_harbor_client
from kinds import ObjectKind
from integration import (
    ProjectResourceConfig,
    UserResourceConfig,
    RepositoryResourceConfig,
    ArtifactResourceConfig,
)


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor projects.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of project data
    """
    logger.info(f"Starting resync for {kind}")

    client = create_harbor_client()

    # Access resource configuration
    resource_config = cast(ProjectResourceConfig, event.resource_config)
    selector = resource_config.selector

    # Build query parameters from selector
    params: dict[str, Any] = {}

    if selector.public is not None:
        params["public"] = selector.public

    if selector.name:
        params["name"] = selector.name

    logger.info(f"Fetching projects with params: {params}")

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received batch of {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor users.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of user data
    """
    logger.info(f"Starting resync for {kind}")

    client = create_harbor_client()

    # Access resource configuration
    resource_config = cast(UserResourceConfig, event.resource_config)
    selector = resource_config.selector

    # Build query parameters from selector
    params: dict[str, Any] = {}

    if selector.username:
        params["q"] = f"username=~{selector.username}"

    logger.info(f"Fetching users with params: {params}")

    async for users in client.get_paginated_users(params):
        logger.info(f"Received batch of {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor repositories.

    Fetches repositories for a specific project if provided,
    otherwise fetches all repositories across projects directly.
    """
    logger.info(f"Starting resync for {kind}")

    client = create_harbor_client()
    resource_config = cast(RepositoryResourceConfig, event.resource_config)
    selector = resource_config.selector

    params: dict[str, Any] = {}

    query_parts = []
    if selector.name_contains:
        query_parts.append(f"name=~{selector.name_contains}")
    if selector.name_starts_with:
        query_parts.append(f"name={selector.name_starts_with}*")

    if query_parts:
        params["q"] = ",".join(query_parts)

    project_name = selector.project_name
    logger.info(f"Fetching repositories for project: {project_name}")

    async for repositories in client.get_paginated_repositories(
        project_name=project_name, params=params
    ):
        logger.info(
            f"Received batch of {len(repositories)} repositories from {project_name}"
        )
        yield repositories


@ocean.on_resync(ObjectKind.ARTIFACT)
async def resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor artifacts.

    This fetches artifacts from all repositories across all projects.

    Args:
        kind: The resource kind being resynced

    Yields:
        Batches of artifact data
    """
    logger.info(f"Starting resync for {kind}")

    client = create_harbor_client()

    # Access resource configuration
    resource_config = cast(ArtifactResourceConfig, event.resource_config)
    selector = resource_config.selector

    # Build artifact query parameters
    artifact_params: dict[str, Any] = {
        "with_tag": selector.with_tag,
        "with_scan_overview": selector.with_scan_overview,
        "with_label": selector.with_label,
    }

    # Build query string for filtering
    query_parts = []

    if selector.tag:
        query_parts.append(f"tags=~{selector.tag}")

    if selector.digest:
        query_parts.append(f"digest={selector.digest}")

    if selector.media_type:
        query_parts.append(f"media_type={selector.media_type}")

    if selector.labels:
        # Format: labels=(label1 label2 label3)
        labels_str = " ".join(selector.labels)
        query_parts.append(f"labels=({labels_str})")

    if query_parts:
        artifact_params["q"] = ",".join(query_parts)

    logger.info(f"Fetching artifacts with params: {artifact_params}")

    # Fetch repositories for this project
    async for repositories in client.get_paginated_repositories():
        for repo in repositories:
            # Extract repository name from full name (format: "project/repo")
            repo_full_name = repo.get("name", "")
            repo_split_name = repo_full_name.split("/")
            repo_name = repo_split_name[-1]
            project_name = repo_split_name[0]

            if not repo_name or not project_name:
                logger.warning(f"Repository or project missing name: {repo}")
                continue

            logger.info(f"Fetching artifacts for {project_name}/{repo_name}")

            # Fetch artifacts for this repository
            async for artifacts in client.get_paginated_artifacts(
                project_name=project_name,
                repository_name=repo_name,
                params=artifact_params,
            ):
                if not artifacts:
                    continue
                logger.info(
                    f"Received batch of {len(artifacts)} artifacts "
                    f"from {project_name}/{repo_name}"
                )

                # Enrich artifacts with project and repository context
                for artifact in artifacts:
                    artifact["_project_name"] = project_name
                    artifact["_repository_name"] = repo_name
                    artifact["_repository_full_name"] = repo_full_name

                yield artifacts


@ocean.on_start()
async def on_start() -> None:
    """
    Called when the integration starts.

    Initializes client and sets up webhooks if configured.
    """
    logger.info("Harbor integration started")
    # Test client initialization
    try:
        client = create_harbor_client()
        logger.info("Harbor client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Harbor client: {e}")
        raise

    # Set up webhooks if app_host is configured
    app_host = ocean.config.base_url

    if not app_host:
        logger.warning(
            "app_host not configured, skipping webhook setup. "
            "Webhooks will not be created automatically."
        )

        return
    logger.info(f"Setting up webhooks with app_host: {app_host}")

    webhook_url = f"{app_host}/integration/webhook"
    webhook_secret = ocean.integration_config.get("webhook_secret")

    try:
        results = await client.setup_webhooks_for_all_projects(
            webhook_url=webhook_url,
            auth_header=webhook_secret,
        )

        logger.info(f"Webhook setup results: {results}")
    except Exception as e:
        logger.error(f"Failed to set up webhooks: {e}")


# Register webhook processors for different resource types
ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)

logger.info("Registered webhook processors for Harbor events")
