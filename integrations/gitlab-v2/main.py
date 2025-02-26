from enum import StrEnum
from typing import Any, Optional
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from clients.base_client import GitLabClient


class ObjectKind(StrEnum):
    PROJECT = "project"
    GROUP = "group"
    ISSUE = "issue"
    MERGE_REQUEST = "merge-request"


_gitlab_client: Optional[GitLabClient] = None


def create_gitlab_client() -> GitLabClient:
    global _gitlab_client
    if _gitlab_client is not None:
        return _gitlab_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config.get("gitlab_host", "https://gitlab.com").rstrip("/")

    if token := integration_config.get("gitlab_token"):
        _gitlab_client = GitLabClient(base_url, token)
        return _gitlab_client
    else:
        raise ValueError("GitLab token not found in configuration")


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitLab-v2 Integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook setup because the event listener is ONCE")
        return

    await setup_application()


async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        logger.warning("No base URL provided, skipping webhook setup")
        return

    client = create_gitlab_client()

    # Setup webhooks


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for projects in client.get_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups in client.get_groups():
        logger.info(f"Received group batch with {len(groups)} groups")
        yield groups


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for issues in client.get_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for merge_requests in client.get_merge_requests():
        logger.info(
            f"Received merge request batch with {len(merge_requests)} merge requests"
        )
        yield merge_requests
