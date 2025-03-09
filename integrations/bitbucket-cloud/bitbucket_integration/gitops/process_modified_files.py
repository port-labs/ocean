from typing import List, Dict, Any, Tuple
from loguru import logger
from bitbucket_integration.client import BitbucketClient
from bitbucket_integration.gitops.generate_entities import (
    generate_entities_from_yaml_file,
)


def determine_file_action(updated_file: Dict[str, Any]) -> Tuple[str, str, str]:
    logger.debug(f"Determining file action for updated file: {updated_file}")
    new_file_path = updated_file.get("old", {}).get("path", "")
    old_file_path = updated_file.get("new", {}).get("path", "")
    if not new_file_path:
        return "deleted", old_file_path, new_file_path
    elif not old_file_path:
        return "added", old_file_path, new_file_path
    return "modified", old_file_path, new_file_path


async def process_file(
    client: BitbucketClient,
    repo: str,
    action: str,
    file_path: str,
    target_path: str,
    old_hash: str,
    new_hash: str,
) -> List[Any]:
    if action == "deleted":
        old_data = await client.get_file_content(repo, old_hash, file_path)
        old_entities = await generate_entities_from_yaml_file(
            old_data, client, old_hash, repo, file_path
        )
        return old_entities, []
    elif action == "added":
        new_data = await client.get_file_content(repo, new_hash, target_path)
        new_entities = await generate_entities_from_yaml_file(
            new_data, client, new_hash, repo, target_path
        )
        return [], new_entities
    else:
        old_data = await client.get_file_content(repo, old_hash, file_path)
        new_data = await client.get_file_content(repo, new_hash, target_path)
        old_entities = await generate_entities_from_yaml_file(
            old_data, client, old_hash, repo, file_path
        )
        new_entities = await generate_entities_from_yaml_file(
            new_data, client, new_hash, repo, target_path
        )
        return old_entities, new_entities
