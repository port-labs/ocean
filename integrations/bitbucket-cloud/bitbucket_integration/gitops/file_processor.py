from typing import List, Dict, Any, Tuple
from loguru import logger
from bitbucket_integration.client import BitbucketClient
from bitbucket_integration.gitops.entity_generator import (
    generate_entities_from_yaml_file,
)
from port_ocean.core.models import Entity


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
    old_file_path: str,
    new_file_path: str,
    old_hash: str,
    new_hash: str,
) -> Tuple[List[Entity], List[Entity]]:
    match action:
        case "deleted":
            old_data = await client.get_file_content(repo, old_hash, old_file_path)
            old_entities = await generate_entities_from_yaml_file(
                old_data, client, old_hash, repo, old_file_path
            )
            return old_entities, []
        case "added":
            new_data = await client.get_file_content(repo, new_hash, new_file_path)
            new_entities = await generate_entities_from_yaml_file(
                new_data, client, new_hash, repo, new_file_path
            )
            return [], new_entities
        case _:
            old_data = await client.get_file_content(repo, old_hash, old_file_path)
            new_data = await client.get_file_content(repo, new_hash, new_file_path)
            old_entities = await generate_entities_from_yaml_file(
                old_data, client, old_hash, repo, old_file_path
            )
            new_entities = await generate_entities_from_yaml_file(
                new_data, client, new_hash, repo, new_file_path
            )
            return old_entities, new_entities
