"""Main entry point for Harbor integration."""

from typing import cast

from loguru import logger

from integration import (
    ArtifactResourceConfig,
    ProjectResourceConfig,
)
from harbor.utils import split_repository_name
from initialize_client import create_harbor_client
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook_processors.artifact_webhook_processor import ArtifactWebhookProcessor


@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor projects from the API.
    
    Yields batches of projects from the Harbor API using pagination.
    Uses the selector configuration from the port-app-config to filter projects.
    
    Args:
        kind: The resource kind being resynced
    
    Yields:
        Batches of project dictionaries
    """
    client = create_harbor_client()
    
    # Get the resource config and selector for this kind
    resource_config = cast(ProjectResourceConfig, event.resource_config)
    selector = resource_config.selector
    
    # Build query parameters from selector
    params = {}
    if selector.public is not None:
        params["public"] = str(selector.public).lower()
    
    logger.info(f"Starting resync for Harbor projects with params: {params}")
    
    # Fetch projects in batches
    async for projects_batch in client.get_projects(
        params=params,
    ):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        yield projects_batch


@ocean.on_resync(Kinds.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor repositories from the API.
    
    Yields batches of repositories from the Harbor API using pagination.
    
    Args:
        kind: The resource kind being resynced
    
    Yields:
        Batches of repository dictionaries
    """
    client = create_harbor_client()
    
    
    # Fetch repositories from Harbor API
    async for repositories_batch in client.get_repositories(params={}):
        logger.info(
            f"Received repository batch with {len(repositories_batch)} repositories"
        )
        yield repositories_batch


@ocean.on_resync(Kinds.ARTIFACT)
async def on_resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor artifacts from the API.
    
    This is a nested resource that requires:
    1. Fetching all repositories
    2. For each repository, fetching artifacts
    
    Yields batches of artifacts from the Harbor API using pagination.
    Uses the selector configuration to filter artifacts.
    
    Args:
        kind: The resource kind being resynced
    
    Yields:
        Batches of artifact dictionaries
    """
    client = create_harbor_client()
    
    # Get the resource config and selector for this kind
    resource_config = cast(ArtifactResourceConfig, event.resource_config)
    selector = resource_config.selector
    
    # Build query parameters from selector
    params = {}
    if selector.tag:
        params["q"] = f"tags={selector.tag}"
    if selector.digest:
        params["digest"] = selector.digest
    if selector.label:
        params["with_label"] = selector.label
    if selector.media_type:
        params["media_type"] = selector.media_type
    if selector.created_since:
        params["q"] = f"creation_time>={selector.created_since}"

    logger.info(
        f"Starting resync for Harbor artifacts with params: {params}")
    
    # First, fetch all repositories to know which artifacts to query
    repositories = []
    async for repositories_batch in client.get_repositories(params={}):
        repositories.extend(repositories_batch)
    
    logger.info(f"Found {len(repositories)} repositories to fetch artifacts from")
    
    # Now fetch artifacts for each repository
    for repository in repositories:
        # The repository name is in format "project_name/repository_name"
        repo_name = repository.get("name", "")
        
        try:
            # Split the repository name to get project and repo
            project_name, repository_name = split_repository_name(repo_name)
        except ValueError as e:
            logger.warning(f"Skipping repository due to invalid name: {str(e)}")
            continue
        
        logger.info(f"Fetching artifacts for repository: {repo_name}")
        
        try:
            async for artifacts_batch in client.get_artifacts_for_repository(
                project_name=project_name,
                repository_name=repository_name,
                params=params,
            ):
                if artifacts_batch:
                    logger.info(
                        f"Received {len(artifacts_batch)} artifacts from {repo_name}"
                    )
                    yield artifacts_batch
                    
        except Exception as e:
            logger.error(
                f"Failed to fetch artifacts for repository {repo_name}: {str(e)}"
            )
            continue


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor users from the API.
    
    Yields batches of users from the Harbor API using pagination.
    
    Args:
        kind: The resource kind being resynced
    
    Yields:
        Batches of user dictionaries
    """
    client = create_harbor_client()
    
    # Fetch users from Harbor API
    async for users_batch in client.get_users(params={}):
        logger.info(f"Received user batch with {len(users_batch)} users")
        yield users_batch


@ocean.on_start()
async def on_start() -> None:
    """Called once when the integration starts."""
    logger.info("Starting Harbor integration")


# Register webhook processors for real-time event handling
ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
