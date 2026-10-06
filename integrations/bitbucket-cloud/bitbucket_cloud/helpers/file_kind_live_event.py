import asyncio
from pathlib import Path
from initialize_client import init_client
from typing import Any, TypedDict
import json
import yaml
from loguru import logger
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.helpers.utils import matches_configured_file

FILE_PROPERTY_PREFIX = "file://"
JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")


class FileObject(TypedDict):
    """Represents a processed file object with its associated metadata."""

    content: Any  # Parsed JSON/YAML structure, or raw scalar/plain-text content
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
    old = diff_stat.get("old") or {}
    new = diff_stat.get("new") or {}
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
    if bitbucket_file is None:
        logger.warning(
            f"Referenced file {file_path} could not be read in {repository} at "
            f"{hash[:12]}, resolving it to null"
        )
        return None

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
    """Resolve any file:// values nested in a parsed file.

    ``hash`` is a commit hash, not a ref name - both callers resolve one before
    getting here, so nested references are read at the same immutable commit as the
    file that declared them. ``branch`` is carried through to the emitted object only.
    """
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
    """Whether a pushed path is one the `file` kind is configured to ingest.

    Delegates to the matcher the resync walk uses, so one `files` selector cannot be
    read two ways. This previously fnmatched the basename alone, which made
    `['*.yaml']` match on push and nothing on resync, and `['conf/README.md']` the
    other way round. An empty `filenames` now matches nothing, as the selector
    documents and as the walk already behaved.
    """
    return matches_configured_file(file_path, filenames, config_path)


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

                if is_deleted:
                    deleted_entity = {
                        "repo": repo,
                        "branch": branch,
                        "metadata": diff_stat,
                    }
                    deleted_raw_results.append(deleted_entity)
                else:
                    raw_data = await webhook_client.get_repository_files(
                        repository, new_hash, file_path
                    )
                    if raw_data is None:
                        # Unlike the resync walk, a push runs no delete phase, so
                        # omitting this file leaves the existing entity alone rather
                        # than reconciling it away. Skipping is the safe default here.
                        logger.warning(
                            f"Skipping {repository}/{file_path} at "
                            f"{new_hash[:12]}: the push reported it but its content "
                            "could not be read"
                        )
                        continue

                    if not skip_parsing:
                        raw_data = parse_file(raw_data, file_path)

                    full_raw_data: FileObject
                    if skip_parsing or not isinstance(raw_data, (dict, list)):
                        full_raw_data = {
                            "content": raw_data,
                            "metadata": diff_stat,
                            "repo": repo,
                            "branch": branch,
                        }
                    else:
                        directory_path = Path(file_path).parent
                        full_raw_data = await check_and_load_file_prefix(
                            raw_data,
                            str(directory_path),
                            repository,
                            new_hash,
                            diff_stat,
                            repo,
                            branch,
                        )
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
