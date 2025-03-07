from typing import List, Dict, Any, Tuple
from loguru import logger
from client import BitbucketClient
from gitops.generate_entities import generate_entities_from_yaml_file


def determine_file_action(updated_file: Dict[str, Any]) -> Tuple[str, str, str]:
    new_file_path = updated_file.get("old", {}).get("path", "")
    old_file_path = updated_file.get("new", {}).get("path", "")

    if not new_file_path:
        return "deleted", old_file_path, old_file_path
    elif not old_file_path:
        return "added", new_file_path, new_file_path
    return "modified", new_file_path, new_file_path


async def process_file(
    client: BitbucketClient,
    workspace: str,
    repo: str,
    action: str,
    file_path: str,
    target_path: str,
) -> List[Any]:
    data = client.get_file_content(workspace, repo, target_path)
    entities = await generate_entities_from_yaml_file(data)
    logger.debug(
        f"Processed {action} file {file_path} with {len(entities) if entities else 0} entities"
    )
    return entities if entities else []
