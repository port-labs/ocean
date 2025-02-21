from enum import StrEnum
from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from clients.base_client import GitLabClient


class ObjectKind(StrEnum):
    PROJECT = "project"


def create_gitlab_client() -> GitLabClient:
    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config.get("gitlab_host", "https://gitlab.com")

    if token := integration_config["gitlab_token"]:
        return GitLabClient(base_url, token)
    else:
        raise ValueError("GitLab token not found in configuration")


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean GitLab integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook setup because the event listener is ONCE")
        return

    await setup_application()


async def setup_application() -> None:
    """Setup application webhooks and any other necessary initialization."""
    base_url = ocean.app.base_url
    if not base_url:
        logger.warning("No base URL provided, skipping webhook setup")
        return

    client = create_gitlab_client()

    # Setup webhooks


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync GitLab projects to Port."""
    client = create_gitlab_client()

    async for projects in client.get_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects
