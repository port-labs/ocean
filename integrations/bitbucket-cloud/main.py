import asyncio
from typing import Union, cast, Any

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from bitbucket_cloud.helpers.utils import ObjectKind

from bitbucket_cloud.webhook_processors.processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from bitbucket_cloud.webhook_processors.processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from bitbucket_cloud.webhook_processors.processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from initialize_client import init_client, init_webhook_client
from integration import (
    BitbucketFolderResourceConfig,
    BitbucketFolderSelector,
    BitbucketFileResourceConfig,
    BitbucketFileSelector,
    RepositoryResourceConfig,
    PullRequestResourceConfig,
)
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.helpers.folder import (
    process_folder_patterns,
)
from bitbucket_cloud.helpers.file_kind import process_file_patterns
from bitbucket_cloud.utils import build_repo_params, build_pull_request_params
from bitbucket_cloud.webhook_processors.options import PullRequestSelectorOptions


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


async def _enrich_repo_with_attached_files(
    client: BitbucketClient,
    repo: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a repository dict with __attachedFiles from the given file paths."""
    repo_slug = repo.get("slug") or repo.get("name", "").replace(" ", "-")
    default_branch = repo.get("mainbranch", {}).get("name", "main")
    attached: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content = await client.get_repository_files(
                repo_slug, default_branch, file_path
            )
            attached[file_path] = content
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {repo_slug}@{default_branch}: {e}"
            )
            attached[file_path] = None

    repo["__attachedFiles"] = attached
    return repo


async def _enrich_repos_batch_with_attached_files(
    client: BitbucketClient,
    repositories: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of repositories with attached files."""
    tasks = [
        _enrich_repo_with_attached_files(client, repo, file_paths)
        for repo in repositories
    ]
    return list(await asyncio.gather(*tasks))


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the workspace."""
    client = init_client()
    selector = cast(RepositoryResourceConfig, event.resource_config).selector
    params: dict[str, Any] = build_repo_params(selector.user_role, selector.repo_query)
    attached_files = selector.attached_files or []
    async for repositories in client.get_repositories(params=params):
        if attached_files:
            repositories = await _enrich_repos_batch_with_attached_files(
                client, repositories, attached_files
            )
        yield repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests from all repositories."""
    client = init_client()
    selector = cast(PullRequestResourceConfig, event.resource_config).selector
    params: dict[str, Any] = build_repo_params(selector.user_role, selector.repo_query)
    options = PullRequestSelectorOptions(
        user_role=selector.user_role,
        repo_query=selector.repo_query,
        pull_request_query=selector.pull_request_query,
    )
    async for repositories in client.get_repositories(params=params):
        tasks = [
            client.get_pull_requests(
                repo.get("slug", repo["name"].lower().replace(" ", "-")),
                params=build_pull_request_params(options),
            )
            for repo in repositories
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch


async def _enrich_folder_with_attached_files(
    client: BitbucketClient,
    folder: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a folder entity with __attachedFiles from the given file paths."""
    repo = folder.get("repo", {})
    repo_slug = repo.get("slug") or repo.get("name", "").replace(" ", "-")
    branch = folder.get("branch", "main")
    attached: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content = await client.get_repository_files(repo_slug, branch, file_path)
            attached[file_path] = content
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {repo_slug}@{branch}: {e}"
            )
            attached[file_path] = None

    folder["__attachedFiles"] = attached
    return folder


async def _enrich_folders_batch_with_attached_files(
    client: BitbucketClient,
    folders: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of folders with attached files."""
    tasks = [
        _enrich_folder_with_attached_files(client, folder, file_paths)
        for folder in folders
    ]
    return list(await asyncio.gather(*tasks))


async def _enrich_file_entity_with_attached_files(
    client: BitbucketClient,
    file_entity: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a file entity with __attachedFiles from the given file paths."""
    repo = file_entity.get("repo", {})
    repo_slug = repo.get("slug") or repo.get("name", "").replace(" ", "-")
    branch = file_entity.get("branch") or repo.get("mainbranch", {}).get("name", "main")
    attached: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content = await client.get_repository_files(repo_slug, branch, file_path)
            attached[file_path] = content
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {repo_slug}@{branch}: {e}"
            )
            attached[file_path] = None

    file_entity["__attachedFiles"] = attached
    return file_entity


async def _enrich_file_entities_batch_with_attached_files(
    client: BitbucketClient,
    file_entities: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of file entities with attached files."""
    tasks = [
        _enrich_file_entity_with_attached_files(client, fe, file_paths)
        for fe in file_entities
    ]
    return list(await asyncio.gather(*tasks))


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    config = cast(
        Union[ResourceConfig, BitbucketFolderResourceConfig], event.resource_config
    )
    selector = cast(BitbucketFolderSelector, config.selector)
    client = init_client()
    params: dict[str, Any] = build_repo_params(selector.user_role, selector.repo_query)
    attached_files = selector.attached_files or []
    async for matching_folders in process_folder_patterns(
        selector.folders,
        client,
        params=params,
    ):
        if attached_files:
            matching_folders = await _enrich_folders_batch_with_attached_files(
                client, matching_folders, attached_files
            )
        yield matching_folders


@ocean.on_resync(ObjectKind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync files based on configuration using optimized query filtering."""
    config = cast(
        Union[ResourceConfig, BitbucketFileResourceConfig], event.resource_config
    )
    selector = cast(BitbucketFileSelector, config.selector)
    attached_files = selector.attached_files or []
    client = init_client() if attached_files else None
    async for file_result in process_file_patterns(selector.files):
        if attached_files and client:
            file_result = await _enrich_file_entities_batch_with_attached_files(
                client, file_result, attached_files
            )
        yield file_result


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", FileWebhookProcessor)
