import asyncio
from typing import Any

from loguru import logger

from bitbucket_cloud.client import BitbucketClient


async def _enrich_folder_with_included_files(
    client: BitbucketClient,
    folder: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a folder entity with __includedFiles from the given file paths."""
    repo = folder.get("repo", {})
    repo_slug = repo.get("slug") or repo.get("name", "").replace(" ", "-")
    branch = folder.get("branch", "main")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content = await client.get_repository_files(repo_slug, branch, file_path)
            included[file_path] = content
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {repo_slug}@{branch}: {e}"
            )
            included[file_path] = None

    folder["__includedFiles"] = included
    return folder


async def _enrich_folders_batch_with_included_files(
    client: BitbucketClient,
    folders: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of folders with included files."""
    tasks = [
        _enrich_folder_with_included_files(client, folder, file_paths)
        for folder in folders
    ]
    return list(await asyncio.gather(*tasks))


async def _enrich_file_entity_with_included_files(
    client: BitbucketClient,
    file_entity: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a file entity with __includedFiles from the given file paths."""
    repo = file_entity.get("repo", {})
    repo_slug = repo.get("slug") or repo.get("name", "").replace(" ", "-")
    branch = file_entity.get("branch") or repo.get("mainbranch", {}).get("name", "main")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content = await client.get_repository_files(repo_slug, branch, file_path)
            included[file_path] = content
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {repo_slug}@{branch}: {e}"
            )
            included[file_path] = None

    file_entity["__includedFiles"] = included
    return file_entity


async def _enrich_file_entities_batch_with_included_files(
    client: BitbucketClient,
    file_entities: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of file entities with included files."""
    tasks = [
        _enrich_file_entity_with_included_files(client, fe, file_paths)
        for fe in file_entities
    ]
    return list(await asyncio.gather(*tasks))
