import asyncio
from pathlib import Path
from initialize_client import init_client
from typing import Any, TypedDict
import json
import yaml
from loguru import logger
from bitbucket_cloud.client import BitbucketClient
from fnmatch import fnmatch


FILE_PROPERTY_PREFIX = "file://"
JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")


class FileObject(TypedDict):
    """Represents a processed file object with its associated metadata."""

    content: (
        dict[str, Any] | list[dict[str, Any]]
    )  # The actual content of the file (parsed JSON/YAML)
    metadata: dict[str, Any]  # Diff statistics and file information
    repo: dict[str, Any]  # Repository information
    branch: str  # Branch name


def extract_hash_from_payload(changes: dict[str, Any]) -> tuple[str, str, str]:
    new_hash = changes["new"]["target"]["hash"]
    old_hash = changes["old"]["target"]["hash"]
    branch = changes["new"]["name"]
    return new_hash, old_hash, branch


def get_file_paths(diff_stat: dict[str, Any]) -> tuple[str, str]:
    """
    Extract file paths from diff statistics.
    """
    old = diff_stat.get("old", {})
    new = diff_stat.get("new", {})
    return old.get("path", ""), new.get("path", "")


def determine_action(diff_stat: dict[str, Any]) -> tuple[bool, bool, bool]:
    """
    Determine the type of change made to a file based on diff statistics.
    """
    old = diff_stat.get("old", {})
    new = diff_stat.get("new", {})
    return not old, bool(old and new), not new


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
        parse_file(bitbucket_file, file_path)
        if file_path.endswith(JSON_FILE_SUFFIX)
        else bitbucket_file
    )


async def process_dict_items(
    data: dict[str, Any],
    parent_directory: str,
    repository: str,
    hash: str,
    client: BitbucketClient,
    diff_stat: dict[str, Any],
    repo: dict[str, Any],
    branch: str,
) -> FileObject:
    tasks = [
        process_file_value(value, parent_directory, repository, hash, client)
        for value in data.values()
    ]
    processed_values = await asyncio.gather(*tasks)

    result = dict(zip(data.keys(), processed_values))
    return FileObject(
        content=result,
        metadata=diff_stat,
        repo=repo,
        branch=branch,
    )


async def process_list_items(
    data: list[dict[str, Any]],
    parent_directory: str,
    repository: str,
    hash: str,
    client: BitbucketClient,
    diff_stat: dict[str, Any],
    repo: dict[str, Any],
    branch: str,
) -> FileObject:
    # Process each file object's content directly
    all_tasks = []
    for file_obj in data:
        tasks = [
            process_file_value(value, parent_directory, repository, hash, client)
            for value in file_obj.values()
        ]
        all_tasks.extend(tasks)

    processed_values = await asyncio.gather(*all_tasks)

    # Reconstruct the results maintaining the original structure
    results = []
    current_index = 0
    for file_obj in data:
        content_length = len(file_obj)
        processed_content = dict(
            zip(
                file_obj.keys(),
                processed_values[current_index : current_index + content_length],
            )
        )
        results.append(processed_content)
        current_index += content_length

    return FileObject(
        content=results,
        metadata=diff_stat,
        repo=repo,
        branch=branch,
    )


async def check_and_load_file_prefix(
    raw_data: dict[str, Any] | list[dict[str, Any]],
    parent_directory: str,
    repository: str,
    hash: str,
    diff_stat: dict[str, Any],
    repo: dict[str, Any],
    branch: str,
) -> FileObject:
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
    else:
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


def check_single_path(file_path: str, filenames: list[str], config_path: str) -> bool:
    path_parts = file_path.split("/")
    file_name = path_parts[-1]
    path_without_file = "/".join(path_parts[:-1])

    filename_match = (
        any(fnmatch(file_name, pattern) for pattern in filenames) if filenames else True
    )

    # Special handling for root directory files
    if not path_without_file and config_path in {"/", ""}:
        path_match = True
    else:
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
                is_added, is_modified, is_deleted = determine_action(diff_stat)
                old_file_path, new_file_path = get_file_paths(diff_stat)
                diff_stat["commit"] = {"hash": new_hash}
                file_path = new_file_path if is_added or is_modified else old_file_path
                diff_stat["path"] = file_path

                if not check_single_path(
                    file_path,
                    selector.files.filenames,
                    selector.files.path,
                ):
                    logger.info(
                        f"Skipping file {file_path} because it doesn't match filename the selector {selector.files.filenames} or path {selector.files.path}"
                    )
                    continue

                raw_data = await webhook_client.get_repository_files(
                    repository, old_hash if is_deleted else new_hash, file_path
                )

                if not skip_parsing:
                    raw_data = parse_file(raw_data, file_path)
                    directory_path = Path(file_path).parent
                    full_raw_data = await check_and_load_file_prefix(
                        raw_data,
                        str(directory_path),
                        repository,
                        old_hash if is_deleted else new_hash,
                        diff_stat,
                        repo,
                        branch,
                    )
                else:
                    full_raw_data = {
                        "content": raw_data,
                        "metadata": diff_stat,
                        "repo": repo,
                        "branch": branch,
                    }
                updated_raw_results.append(dict(full_raw_data))
    return updated_raw_results, deleted_raw_results


def parse_file(file: Any, file_path: str) -> Any:
    """Parse a file based on its extension."""
    try:
        if file_path.endswith(JSON_FILE_SUFFIX):
            loaded_file = json.loads(file)
            file = loaded_file
        elif file_path.endswith(YAML_FILE_SUFFIX):
            loaded_file = yaml.safe_load(file)
            file = loaded_file
        return file
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        return file
