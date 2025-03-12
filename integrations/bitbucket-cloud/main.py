from typing import Union, cast

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import BitbucketClient, ObjectKind
from integration import BitbucketFolderResourceConfig, BitbucketFolderSelector
from helpers.folder import (
    process_folder_patterns,
)


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Bitbucket integration")


def init_client() -> BitbucketClient:
    return BitbucketClient.create_from_ocean_config()


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all projects in the workspace."""
    client = init_client()
    async for projects in client.get_projects():
        yield projects


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the workspace."""
    client = init_client()
    async for repositories in client.get_repositories():
        yield repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests from all repositories."""
    client = init_client()
    async for repositories in client.get_repositories():
        for repo in repositories:
            repo_slug = repo.get("slug", repo["name"].lower())
            async for pull_requests in client.get_pull_requests(repo_slug):
                yield pull_requests


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    config = cast(
        Union[ResourceConfig, BitbucketFolderResourceConfig], event.resource_config
    )
    selector = cast(BitbucketFolderSelector, config.selector)
    client = init_client()
    async for matching_folders in process_folder_patterns(selector.folders, client):
        yield matching_folders
