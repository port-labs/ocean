"""Main entry point for Harbor integration."""

import asyncio
from typing import cast

from loguru import logger

from integration import (
    ArtifactResourceConfig,
    ProjectResourceConfig,
)
from harbor.utils import create_artifact_iterator, split_repository_name
from initialize_client import get_harbor_client
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from webhook_processors.artifact_webhook_processor import ArtifactWebhookProcessor


@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor projects from the API.
    """
    client = get_harbor_client()
    
    resource_config = cast(ProjectResourceConfig, event.resource_config)
    selector = resource_config.selector
    
    params = {}
    public = getattr(selector, "public", None)
    if public is not None:
        params["public"] = str(public).lower()
    
    logger.info(f"Starting resync for Harbor projects with params: {params}")
    
    async for projects_batch in client.get_projects(
        params=params,
    ):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        yield projects_batch


@ocean.on_resync(Kinds.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor repositories from the API.
    """
    client = get_harbor_client()
    
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
    """
    client = get_harbor_client()
    
    resource_config = cast(ArtifactResourceConfig, event.resource_config)
    selector = resource_config.selector
    
    params = {}
    tag = getattr(selector, "tag", None)
    digest = getattr(selector, "digest", None)
    label = getattr(selector, "label", None)
    media_type = getattr(selector, "media_type", None)
    created_since = getattr(selector, "created_since", None)
    
    if tag:
        params["q"] = f"tags={tag}"
    if digest:
        params["digest"] = digest
    if label:
        params["with_label"] = label
    if media_type:
        params["media_type"] = media_type
    if created_since:
        params["q"] = f"creation_time>={created_since}"

    logger.info(
        f"Starting resync for Harbor artifacts with params: {params}")
    
    semaphore = asyncio.Semaphore(10)
    
    async for repositories_batch in client.get_repositories(params={}):
        if not repositories_batch:
            continue
            
        logger.info(
            f"Processing batch of {len(repositories_batch)} repositories for artifacts"
        )
        
        tasks = []
        for repository in repositories_batch:
            repo_name = repository.get("name", "")
            
            try:
                project_name, repository_name = split_repository_name(repo_name)
            except ValueError as e:
                logger.warning(f"Skipping repository due to invalid name: {str(e)}")
                continue
            
            tasks.append(
                semaphore_async_iterator(
                    semaphore,
                    lambda p=project_name, r=repository_name, n=repo_name: create_artifact_iterator(
                        client, p, r, n, params
                    ),
                )
            )
        
        if tasks:
            async for artifacts_batch in stream_async_iterators_tasks(*tasks):
                yield artifacts_batch


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync Harbor users from the API.
    """
    client = get_harbor_client()
    
    async for users_batch in client.get_users(params={}):
        logger.info(f"Received user batch with {len(users_batch)} users")
        yield users_batch


@ocean.on_start()
async def on_start() -> None:
    """Called once when the integration starts."""
    logger.info("Starting Harbor integration")


# Register webhook processors for real-time event handling
ocean.add_webhook_processor("/webhook", ArtifactWebhookProcessor)
