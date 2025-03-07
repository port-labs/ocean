from typing import List, Any, Dict, Tuple, Optional
from loguru import logger
from client import BitbucketClient
from gitops.match_path import match_spec_paths
from gitops.process_modified_files import determine_file_action, process_file


async def process_single_file(
    client: BitbucketClient,
    workspace: str,
    repo: str,
    updated_file: Dict[str, Any],
    spec_paths: Any,
) -> Optional[Tuple[List[Any], List[Any]]]:
    action, file_path, target_path = determine_file_action(updated_file)

    matching_paths = match_spec_paths(file_path, spec_paths)
    if not matching_paths:
        logger.debug(f"File {file_path} does not match spec path pattern(s), skipping")
        return None

    entities = await process_file(
        client, workspace, repo, action, file_path, target_path
    )
    if not entities:
        return None

    if action == "deleted":
        return [], entities
    return entities, []


async def process_diff_stats(
    client: BitbucketClient,
    workspace: str,
    repo: str,
    spec_paths: Any,
    old_hash: str,
    new_hash: str,
) -> Tuple[List[Any], List[Any]]:
    all_updates = []
    all_deletes = []

    async for diff_stats in client.retrieve_diff_stat(
        workspace=workspace, repo=repo, old_hash=old_hash, new_hash=new_hash
    ):
        for diff_stat in diff_stats:
            for updated_file in diff_stat:
                file_changes = await process_single_file(
                    client, workspace, repo, updated_file, spec_paths
                )
                if file_changes:
                    updates, deletes = file_changes
                    all_updates.extend(updates)
                    all_deletes.extend(deletes)

    return all_updates, all_deletes
