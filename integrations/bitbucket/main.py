from typing import Union, cast

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from integration import BitbucketFolderResourceConfig, BitbucketFolderSelector
from bitbucket_integration.helpers.folder import (
    extract_repo_names_from_patterns,
    create_pattern_mapping,
    find_matching_folders,
)
from bitbucket_integration.webhook.processors.pull_request import (
    PullRequestWebhookProcessor,
)
from bitbucket_integration.webhook.processors.repository import (
    RepositoryWebhookProcessor,
)

from initialize_client import init_client, init_webhook_client
from bitbucket_integration.utils import ObjectKind


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Bitbucket integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        logger.warning("No base URL configured, skipping webhook creation")
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
    folder_patterns = selector.folders
    repo_names = extract_repo_names_from_patterns(folder_patterns)
    if not repo_names:
        return
    client = init_client()
    pattern_by_repo = create_pattern_mapping(folder_patterns)
    async for repos_batch in client.get_repositories():
        for repo in repos_batch:
            repo_name = repo["name"]
            if repo_name not in repo_names or repo_name not in pattern_by_repo:
                continue
            patterns = pattern_by_repo[repo_name]
            repo_slug = repo.get("slug", repo_name.lower())
            default_branch = repo.get("mainbranch", {}).get("name", "master")
            max_pattern_depth = max(
                (
                    folder_pattern.path.count("/") + 1
                    for folder_pattern in folder_patterns
                ),
                default=1,
            )
            async for contents in client.get_directory_contents(
                repo_slug, default_branch, "", max_depth=max_pattern_depth
            ):
                matching_folders = find_matching_folders(contents, patterns, repo)
                if matching_folders:
                    yield matching_folders


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
