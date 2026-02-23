import asyncio
from typing import Any

from loguru import logger

from github.core.exporters.file_exporter import RestFileExporter
from github.core.options import FileContentOptions


async def _enrich_folder_with_included_files(
    rest_client: Any,
    folder: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a folder entity with __includedFiles from the given file paths."""
    repo = folder.get("__repository", {})
    organization = folder.get("__organization", "")
    repo_name = repo.get("name", "")
    default_branch = repo.get("default_branch")
    included: dict[str, Any] = {}
    file_exporter = RestFileExporter(rest_client)

    for file_path in file_paths:
        try:
            response = await file_exporter.get_resource(
                FileContentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    file_path=file_path,
                    branch=default_branch,
                )
            )
            included[file_path] = response.get("content") if response else None
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {organization}/{repo_name}: {e}"
            )
            included[file_path] = None

    folder["__includedFiles"] = included
    return folder


async def _enrich_folders_batch_with_included_files(
    rest_client: Any,
    folders: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of folders with included files."""
    tasks = [
        _enrich_folder_with_included_files(rest_client, folder, file_paths)
        for folder in folders
    ]
    return list(await asyncio.gather(*tasks))


async def _enrich_file_entity_with_included_files(
    rest_client: Any,
    file_entity: dict[str, Any],
    file_paths: list[str],
) -> dict[str, Any]:
    """Enrich a file entity with __includedFiles from the given file paths."""
    organization = file_entity.get("organization", "")
    repo = file_entity.get("repository", {})
    repo_name = repo.get("name", "") if isinstance(repo, dict) else ""
    branch = file_entity.get("branch")
    included: dict[str, Any] = {}
    file_exporter = RestFileExporter(rest_client)

    for file_path in file_paths:
        try:
            response = await file_exporter.get_resource(
                FileContentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    file_path=file_path,
                    branch=branch,
                )
            )
            included[file_path] = response.get("content") if response else None
        except Exception as e:
            logger.debug(
                f"Could not fetch file {file_path} from {organization}/{repo_name}: {e}"
            )
            included[file_path] = None

    file_entity["__includedFiles"] = included
    return file_entity


async def _enrich_file_entities_batch_with_included_files(
    rest_client: Any,
    file_entities: list[dict[str, Any]],
    file_paths: list[str],
) -> list[dict[str, Any]]:
    """Enrich a batch of file entities with included files."""
    tasks = [
        _enrich_file_entity_with_included_files(rest_client, fe, file_paths)
        for fe in file_entities
    ]
    return list(await asyncio.gather(*tasks))
