from enum import StrEnum
import fnmatch
from typing import Any, Union, cast

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import BitbucketClient
from integration import BitbucketFolderResourceConfig, BitbucketFolderSelector


class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Bitbucket integration")


async def init_client() -> BitbucketClient:
    client = BitbucketClient(
        workspace=ocean.integration_config["bitbucket_workspace"],
        username=ocean.integration_config.get("bitbucket_username"),
        app_password=ocean.integration_config.get("bitbucket_app_password"),
        workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
    )
    return client


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all projects in the workspace."""
    client = await init_client()
    async for projects in client.get_projects():
        yield projects


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the workspace."""
    client = await init_client()
    async for repositories in client.get_repositories():
        yield repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests from all repositories."""
    client = await init_client()
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

    if not folder_patterns:
        logger.info("No folder patterns found in config, skipping folder sync")
        return
    repo_names = {
        repo_name for pattern in folder_patterns for repo_name in pattern.repos
    }
    if not repo_names:
        logger.info("No repository names found in patterns, skipping folder sync")
        return
    client = await init_client()
    repositories = {}
    pattern_by_repo: dict[str, Any] = {}
    for pattern in folder_patterns:
        for repo_name in pattern.repos:
            if repo_name not in pattern_by_repo:
                pattern_by_repo[repo_name] = []
            pattern_by_repo[repo_name].append(pattern.path)

    async for repos_batch in client.get_repositories():
        for repo in repos_batch:
            if repo["name"] in repo_names:
                repositories[repo["name"]] = repo

    for repo_name, patterns in pattern_by_repo.items():
        if repo_name not in repositories:
            continue

        repo = repositories[repo_name]
        repo_slug = repo.get("slug", repo_name.lower())
        default_branch = repo.get("mainbranch", {}).get("name", "master")
        max_pattern_depth = max(
            (folder_pattern.path.count("/") + 1 for folder_pattern in folder_patterns),
            default=1,
        )

        async for contents in client.get_directory_contents(
            repo_slug, default_branch, "", max_depth=max_pattern_depth
        ):
            matching_folders = []
            for pattern_str in patterns:
                is_wildcard_pattern = any(c in pattern_str for c in "*?[]")
                matching = [
                    {"folder": folder, "repo": repo, "pattern": pattern_str}
                    for folder in contents
                    if folder["type"] == "commit_directory"
                    and (
                        (
                            is_wildcard_pattern
                            and folder["path"].count("/") == pattern_str.count("/")
                        )
                        or (not is_wildcard_pattern and folder["path"] == pattern_str)
                    )
                    and fnmatch.fnmatch(folder["path"], pattern_str)
                ]
                matching_folders.extend(matching)
            if matching_folders:
                yield matching_folders
