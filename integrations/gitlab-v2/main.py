from enum import StrEnum
from typing import Any, Optional, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.base_client import GitLabClient
from integration import ProjectResourceConfig


class ObjectKind(StrEnum):
    PROJECT = "project"
    GROUP = "group"
    ISSUE = "issue"
    MERGE_REQUEST = "merge-request"
    LABELS = "labels"


_gitlab_client: Optional[GitLabClient] = None


def create_gitlab_client() -> GitLabClient:
    global _gitlab_client
    if _gitlab_client is not None:
        return _gitlab_client

    integration_config: dict[str, Any] = ocean.integration_config
    base_url = integration_config["gitlab_host"].rstrip("/")

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


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(ProjectResourceConfig, event.resource_config).selector

    async for projects_batch in client.get_projects():
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        if selector.include_labels:
            for project in projects_batch:
                if labels := project.get("labels", {}).get("nodes"):
                    project["__labels"] = labels

        yield projects_batch


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups in client.get_groups():
        logger.info(f"Received group batch with {len(groups)} groups")
        yield groups


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Processing batch of {len(groups_batch)} groups for issues")

        for group in groups_batch:
            async for issues_batch in client.get_group_resource(group, "issues"):
                logger.info(f"Received issue batch with {len(issues_batch)} issues")
                yield issues_batch


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(
            f"Processing batch of {len(groups_batch)} groups for merge requests"
        )

        for group in groups_batch:
            async for mrs_batch in client.get_group_resource(group, "merge_requests"):
                logger.info(f"Received mrs_batch with {len(mrs_batch)} mrs")
                yield mrs_batch


@ocean.on_resync(ObjectKind.LABELS)
async def on_resync_labels(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(f"Processing batch of {len(groups_batch)} groups for labels")

        for group in groups_batch:
            async for labels_batch in client.get_group_resource(group, "labels"):
                logger.info(f"Received labels batch with {len(labels_batch)} labels")
                yield labels_batch
