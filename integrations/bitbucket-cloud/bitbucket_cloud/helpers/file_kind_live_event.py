import asyncio
from pathlib import Path
from initialize_client import init_client
from typing import Any, Optional
import json
import yaml
from loguru import logger
from bitbucket_cloud.client import BitbucketClient
from fnmatch import fnmatch


FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"
YAML_SUFFIX = ".yaml"


def extract_hash_from_payload(changes: dict[str, Any]) -> tuple[str, str, str]:
    new_hash = changes["new"]["hash"]
    old_hash = changes["old"]["hash"]
    branch = changes["new"]["name"]
    return new_hash, old_hash, branch


def determine_action(diff_stat: dict[str, Any]) -> tuple[str, str, str]:
    old = diff_stat.get("old", {})
    new = diff_stat.get("new", {})
    old_file_path = old["path"] if old else ""
    new_file_path = new["path"] if new else ""
    if not old:
        return "added", old_file_path, new_file_path
    elif not new:
        return "deleted", old_file_path, new_file_path
    return "modified", old_file_path, new_file_path


async def process_file_value(
    value: str,
    parent_directory: str,
    repository: str,
    hash: str,
    client: BitbucketClient,
) -> Any:
    if not isinstance(value, str) or not value.startswith(FILE_PROPERTY_PREFIX):
        return value

    file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
    file_path = f"{parent_directory}/{file_meta}"
    bitbucket_file = await client.get_repository_files(repository, hash, file_path)

    return (
        json.loads(bitbucket_file)
        if Path(file_path).suffix == JSON_SUFFIX
        else bitbucket_file
    )


async def process_dict_items(
    data: dict[str, Any],
    parent_directory: str,
    repository: str,
    hash: str,
    client: BitbucketClient,
    diff_stat: Optional[dict[str, Any]] = None,
    repo: Optional[dict[str, Any]] = None,
    branch: Optional[str] = None,
) -> dict[str, Any]:
    tasks = [
        process_file_value(value, parent_directory, repository, hash, client)
        for value in data.values()
    ]
    processed_values = await asyncio.gather(*tasks)

    result = dict(zip(data.keys(), processed_values))
    if diff_stat and repo and branch:
        result = {
            "content": result,
            "metadata": diff_stat,
            "repo": repo,
            "branch": branch,
        }
    return result


async def process_list_items(
    data: list[dict[str, Any]],
    parent_directory: str,
    repository: str,
    hash: str,
    client: BitbucketClient,
    diff_stat: dict[str, Any],
    repo: dict[str, Any],
    branch: str,
) -> dict[str, Any]:
    tasks = [
        process_dict_items(item, parent_directory, repository, hash, client)
        for item in data
    ]
    results = await asyncio.gather(*tasks)
    return {
        "content": results,
        "metadata": diff_stat,
        "repo": repo,
        "branch": branch,
    }


async def check_and_load_file_prefix(
    raw_data: Any,
    parent_directory: str,
    repository: str,
    hash: str,
    diff_stat: dict[str, Any],
    repo: dict[str, Any],
    branch: str,
) -> dict[str, Any]:
    client = init_client()

    if isinstance(raw_data, dict):
        return await process_dict_items(
            raw_data,
            parent_directory,
            repository,
            hash,
            client,
            diff_stat,
            repo,
            branch,
        )
    elif isinstance(raw_data, list):
        return await process_list_items(
            raw_data,
            parent_directory,
            repository,
            hash,
            client,
            diff_stat,
            repo,
            branch,
        )
    return raw_data


def check_single_path(file_path: str, filenames: list[str], config_path: str) -> bool:
    path_parts = file_path.split("/")
    file_name = path_parts[-1]
    path_without_file = "/".join(path_parts[:-1])

    filename_match = (
        any(fnmatch(file_name, pattern) for pattern in filenames) if filenames else True
    )
    path_match = fnmatch(path_without_file, config_path) if config_path else True

    return filename_match and path_match


async def process_file_changes(
    repository: str,
    changes: list[dict[str, Any]],
    selector: Any,
    skip_parsing: bool,
    webhook_client: Any,
    payload: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    updated_raw_results: list[dict[str, Any]] = []
    deleted_raw_results: list[dict[str, Any]] = []
    repo = payload["repository"]

    for change in changes:
        new_hash, old_hash, branch = extract_hash_from_payload(change)
        async for diff_stats in webhook_client.retrieve_diff_stat(
            repo=repository, old_hash=old_hash, new_hash=new_hash
        ):
            for diff_stat in diff_stats:
                logger.debug(f"Diff stats: {diff_stat}")
                action, old_file_path, new_file_path = determine_action(diff_stat)
                diff_stat["commit"]["hash"] = new_hash
                file_path = old_file_path if action == "deleted" else new_file_path

                if not check_single_path(
                    file_path,
                    selector.files.filenames,
                    selector.files.path,
                ):
                    continue

                raw_data = await webhook_client.get_repository_files(
                    repository, old_hash if action == "deleted" else new_hash, file_path
                )

                if not skip_parsing:
                    if file_path.endswith(YAML_SUFFIX):
                        raw_data = yaml.safe_load(raw_data)
                    elif file_path.endswith(JSON_SUFFIX):
                        raw_data = json.loads(raw_data)

                directory_path = Path(file_path).parent
                full_raw_data = await check_and_load_file_prefix(
                    raw_data,
                    str(directory_path),
                    repository,
                    old_hash if action == "deleted" else new_hash,
                    diff_stat,
                    repo,
                    branch,
                )
                updated_raw_results.append(full_raw_data)

    return updated_raw_results, deleted_raw_results
