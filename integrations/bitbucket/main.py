from enum import StrEnum
from typing import Any, Dict
import fnmatch

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import BitbucketClient


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


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync folders based on configuration."""
    selector = event.resource_config.get("selector", {})
    folder_patterns = selector.get("folders", [])

    if not folder_patterns:
        logger.info("No folder patterns found in config, skipping folder sync")
        return

    repo_names = {
        repo_name
        for pattern in folder_patterns
        for repo_name in pattern.get("repos", [])
    }

    if not repo_names:
        logger.info("No repository names found in patterns, skipping folder sync")
        return

    client = await init_client()
    repositories = {}
    pattern_by_repo = {}

    for pattern in folder_patterns:
        for repo_name in pattern.get("repos", []):
            if repo_name not in pattern_by_repo:
                pattern_by_repo[repo_name] = []
            pattern_by_repo[repo_name].append(pattern.get("path", ""))

    async for repos_batch in client.get_repositories():
        for repo in repos_batch:
            if repo["name"] in repo_names:
                repositories[repo["name"]] = repo

    for repo_name, patterns in pattern_by_repo.items():
        if repo_name not in repositories:
            logger.warning(f"Repository {repo_name} not found, skipping")
            continue

        repo = repositories[repo_name]
        repo_slug = repo.get("slug", repo_name.lower())
        default_branch = repo.get("mainbranch", {}).get("name", "master")

        async for contents in client.get_directory_contents(
            repo_slug, default_branch, ""
        ):
            matching_folders = []
            for pattern in patterns:
                matching = [
                    {"folder": folder, "repo": repo, "pattern": pattern}
                    for folder in contents
                    if folder["type"] == "directory"
                    and fnmatch.fnmatch(folder["path"], pattern)
                ]
                matching_folders.extend(matching)

            if matching_folders:
                yield matching_folders


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

    repos = []
    async for repositories in client.get_repositories():
        repos.extend(repositories)

    for repo in repos:
        repo_slug = repo.get("slug", repo["name"].lower())
        async for pull_requests in client.get_pull_requests(repo_slug):
            yield pull_requests
