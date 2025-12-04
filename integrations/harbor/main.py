"""Main module."""

import logging

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from harbor_integration.config import HarborConfig

from harbor_integration.client import HarborClient
from harbor_integration.handlers import (
    get_projects,
    get_repositories,
    get_artifacts,
    get_users,
)
from harbor_integration.integration import HarborKind

logger = logging.getLogger(__name__)


def initialize_client() -> HarborClient:
    """Initialize Harbor client."""
    config = HarborConfig(
        base_url=ocean.integration_config["harbor_url"],
        username=ocean.integration_config["harbor_username"],
        password=ocean.integration_config["harbor_password"],
    )
    return HarborClient(config)


@ocean.on_resync(HarborKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor projects."""

    harbor_client = initialize_client()
    async for projects in get_projects(harbor_client, harbor_client.config):
        yield projects


@ocean.on_resync(HarborKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor repositories."""

    harbor_client = initialize_client()
    async for repositories in get_repositories(harbor_client):
        yield repositories


@ocean.on_resync(HarborKind.ARTIFACT)
async def on_resync_artifacts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor artifacts."""

    harbor_client = initialize_client()
    async for artifacts in get_artifacts(harbor_client, harbor_client.config):
        yield artifacts


@ocean.on_resync(HarborKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync Harbor users."""

    harbor_client = initialize_client()
    async for users in get_users(harbor_client):
        yield users


@ocean.on_start()
async def on_start() -> None:
    """Start Harbor integration."""
    logger.info("Starting Port Ocean Harbor integration")
    _ = initialize_client()
    logger.info("Harbor integration initialized")
