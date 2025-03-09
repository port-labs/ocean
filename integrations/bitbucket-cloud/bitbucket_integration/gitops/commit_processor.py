from typing import List, Any, Dict, Tuple, Optional
from loguru import logger
from bitbucket_integration.client import BitbucketClient
from bitbucket_integration.gitops.match_path import match_spec_paths
from bitbucket_integration.gitops.process_modified_files import (
    determine_file_action,
    process_file,
)


async def process_single_file(
    client: BitbucketClient,
    repo: str,
    updated_file: Dict[str, Any],
    spec_paths: Any,
    old_hash: str,
    new_hash: str,
) -> Tuple[List[Any], List[Any]]:
    action, file_path, target_path = determine_file_action(updated_file)

    matching_paths = match_spec_paths(file_path, target_path, spec_paths)
    if not matching_paths:
        logger.debug(f"File {file_path} does not match spec path pattern(s), skipping")
        return [], []

    old_entities, new_entities = await process_file(
        client, repo, action, file_path, target_path, old_hash, new_hash
    )
    return old_entities, new_entities


async def process_diff_stats(
    client: BitbucketClient,
    repo: str,
    spec_paths: Any,
    old_hash: str,
    new_hash: str,
) -> Tuple[List[Any], List[Any]]:
    all_old_entities = []
    all_new_entities = []
    logger.debug(
        f"Processing diff stats for repo: {repo}, old_hash: {old_hash}, new_hash: {new_hash}"
    )
    async for diff_stats in client.retrieve_diff_stat(
        repo=repo, old_hash=old_hash, new_hash=new_hash
    ):
        logger.debug(f"Diff stats: {diff_stats}")
        for diff_stat in diff_stats:
            old_entities, new_entities = await process_single_file(
                client, repo, diff_stat, spec_paths, old_hash, new_hash
            )
            all_old_entities.extend(old_entities)
            all_new_entities.extend(new_entities)
            logger.debug(
                f"Old entities: {old_entities}, New entities: {new_entities}; process_diff_stats"
            )

    return all_old_entities, all_new_entities
