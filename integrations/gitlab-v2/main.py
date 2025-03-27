from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.client_factory import create_gitlab_client
from helpers.utils import ObjectKind
from integration import (
    GitLabFilesResourceConfig,
    ProjectResourceConfig,
    GitLabFoldersResourceConfig,
)


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitLab-v2 Integration")


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(ProjectResourceConfig, event.resource_config).selector

    include_languages = bool(selector.include_languages)

    async for projects_batch in client.get_projects(
        include_languages=include_languages
    ):
        logger.info(f"Received project batch with {len(projects_batch)} projects")
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
        async for issues_batch in client.get_groups_resource(groups_batch, "issues"):
            yield issues_batch


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    async for groups_batch in client.get_groups():
        logger.info(
            f"Processing batch of {len(groups_batch)} groups for merge requests"
        )
        async for merge_requests_batch in client.get_groups_resource(
            groups_batch, "merge_requests"
        ):
            yield merge_requests_batch


@ocean.on_resync(ObjectKind.FILE)
async def on_resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()

    selector = cast(GitLabFilesResourceConfig, event.resource_config).selector

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


@ocean.on_resync(ObjectKind.FOLDER)
async def on_resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_gitlab_client()
    selector = cast(GitLabFoldersResourceConfig, event.resource_config).selector

    for folder_selector in selector.folders:
        path = folder_selector.path
        repos = folder_selector.repos if folder_selector.repos else None
        branch = folder_selector.branch

        if not repos:
            logger.info(
                f"No repositories specified for path {path}; skipping folder resync"
            )
            continue

        async for folders_batch in client.search_folders(path, repos, branch):
            if folders_batch:
                logger.info(f"Found batch of {len(folders_batch)} matching folders")
                yield folders_batch
