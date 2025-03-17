from typing import Any, Optional, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.gitlab_client import GitLabClient
from integration import ProjectResourceConfig
from utils import ObjectKind

_gitlab_client: Optional[GitLabClient] = None


def create_gitlab_client() -> GitLabClient:
    global _gitlab_client
    if _gitlab_client is not None:
        return _gitlab_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["gitlab_host"].rstrip("/")
    _gitlab_client = GitLabClient(base_url, integration_config["gitlab_token"])
    return _gitlab_client


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitLab-v2 Integration")


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(ProjectResourceConfig, event.resource_config).selector

    async for projects_batch in client.get_projects():
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        if selector.include_labels:
            for project in projects_batch:
                project["__labels"] = (
                    project["labels"]["nodes"]
                    if "labels" in project and "nodes" in project["labels"]
                    else []
                )
        yield projects_batch


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Received group batch with {len(groups_batch)} groups")
        yield groups_batch


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Processing batch of {len(groups_batch)} groups for issues")
        async for issues_batch in client.get_group_resource(groups_batch, "issues"):
            yield issues_batch


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(
            f"Processing batch of {len(groups_batch)} groups for merge requests"
        )
        async for mrs_batch in client.get_group_resource(
            groups_batch, "merge_requests"
        ):
            yield mrs_batch


@ocean.on_resync(ObjectKind.LABELS)
async def on_resync_labels(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Processing batch of {len(groups_batch)} groups for labels")
        async for labels_batch in client.get_group_resource(groups_batch, "labels"):
            yield labels_batch
