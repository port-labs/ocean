from typing import Any, Optional, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.gitlab_client import GitLabClient
from integration import ProjectResourceConfig, GitLabFilesResourceConfig
from gitops.utils import get_file_paths
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

    include_labels = bool(selector.include_labels)
    params = {"includeLabels": include_labels}

    params = {
        "includeLabels": include_labels,
    }

    if event.resource_config:
        mappings = event.resource_config.port.entity.mappings
        if file_paths := get_file_paths(mappings):
            params["filePaths"] = file_paths

    async for projects_batch in client.get_projects(params):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
        if include_labels:
            for project in projects_batch:
                project["__labels"] = project["labels"]["nodes"]

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


@ocean.on_resync(ObjectKind.FILE)
async def on_resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(GitLabFilesResourceConfig, event.resource_config).selector

    if not selector.files or not selector.files.path:
        logger.warning("No path provided in the selector, skipping fetching files")
        return

    search_path = selector.files.path

    repos = (
        selector.files.repos
        if hasattr(selector.files, "repos") and selector.files.repos
        else None
    )

    async for files_batch in client.search_files(search_path, repos):
        if files_batch:
            logger.info(f"Found batch of {len(files_batch)} matching files")
            yield files_batch
