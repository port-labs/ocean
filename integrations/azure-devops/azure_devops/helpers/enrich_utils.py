import asyncio
from typing import Any

from loguru import logger

from azure_devops.client.azure_devops_client import AzureDevopsClient


async def _enrich_folder_with_included_files(
    client: AzureDevopsClient,
    folder: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a folder entity with __includedFiles from the given file paths."""
    repo = folder.get("__repository", {})
    repo_id = repo.get("id", "")
    branch = folder.get("__branch") or repo.get(
        "defaultBranch", "refs/heads/main"
    ).replace("refs/heads/", "")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content_bytes = await client.get_file_by_branch(file_path, repo_id, branch)
            included[file_path] = (
                content_bytes.decode("utf-8") if content_bytes else None
            )
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from repo {repo.get('name', repo_id)}@{branch}: {e}"
            )
            included[file_path] = None

    folder["__includedFiles"] = included
    return folder


async def _enrich_folders_batch_with_included_files(
    client: AzureDevopsClient,
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
    client: AzureDevopsClient,
    file_entity: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a file entity with __includedFiles from the given file paths."""
    repo = file_entity.get("repo", {})
    repo_id = repo.get("id", "")
    branch = repo.get("defaultBranch", "refs/heads/main").replace("refs/heads/", "")
    included: dict[str, Any] = {}

    for file_path in file_paths:
        try:
            content_bytes = await client.get_file_by_branch(file_path, repo_id, branch)
            included[file_path] = (
                content_bytes.decode("utf-8") if content_bytes else None
            )
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from repo {repo.get('name', repo_id)}@{branch}: {e}"
            )
            included[file_path] = None

    file_entity["__includedFiles"] = included
    return file_entity


async def _enrich_file_entities_batch_with_included_files(
    client: AzureDevopsClient,
    file_entities: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of file entities with included files."""
    tasks = [
        _enrich_file_entity_with_included_files(client, fe, file_paths)
        for fe in file_entities
    ]
    return list(await asyncio.gather(*tasks))
