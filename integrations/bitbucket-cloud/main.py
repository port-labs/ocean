from typing import Union, cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from bitbucket_cloud.helpers.utils import ObjectKind

from bitbucket_cloud.webhook_processors.processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from bitbucket_cloud.webhook_processors.processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from initialize_client import init_client, init_webhook_client, init_multiple_client
from integration import BitbucketFolderResourceConfig, BitbucketFolderSelector
from bitbucket_cloud.helpers.folder import (
    process_folder_patterns,
)

MANAGER = init_multiple_client()


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Bitbucket integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    webhook_client = init_webhook_client()
    await webhook_client.create_webhook(base_url)


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all projects in the workspace."""
    client = init_client()
    async for projects in client.get_projects():
        yield projects


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the workspace using the client manager."""
    async for repositories in MANAGER.execute_request("get_repositories"):
        yield repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests from all repositories."""
    async for repositories in MANAGER.execute_request("get_pull_requests"):
        yield repositories


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    config = cast(
        Union[ResourceConfig, BitbucketFolderResourceConfig], event.resource_config
    )
    selector = cast(BitbucketFolderSelector, config.selector)
    async for matching_folders in process_folder_patterns(selector.folders, MANAGER):
        yield matching_folders


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
