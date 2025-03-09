import json
from pathlib import Path
from typing import Any, AsyncGenerator, Optional
from loguru import logger
import yaml
from bitbucket_integration.client import BitbucketClient
from port_ocean.core.handlers.webhook.webhook_event import EventPayload
from port_ocean.core.models import Entity
from bitbucket_integration.gitops.file_entity_handler import (
    FILE_PROPERTY_PREFIX,
    JSON_SUFFIX,
)


async def get_commit_hash_from_payload(
    payload: EventPayload,
) -> AsyncGenerator[tuple[str, str, str], None]:
    try:
        push_changes = payload.get("push", {}).get("changes", [])
        for change in push_changes:
            commits = change.get("commits", [])
            new = change.get("new", {})
            old = change.get("old", {})
            old_commit = old.get("target", {}).get("hash", "")
            new_commit = new.get("target", {}).get("hash", "")
            branch = new.get("name", "") or old.get("name", "")
            yield new_commit, old_commit, branch
        return
    except Exception as e:
        logger.error(f"Error processing push event: {e}")
        return


async def _generate_entity_from_port_yaml(
    raw_entity: Entity,
    client: BitbucketClient,
    commit_id: str,
    repository_id: str,
) -> Entity:
    properties = {}
    for key, value in raw_entity.properties.items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
            file_content: Any = await client.get_file_content(
                repo=repository_id,
                branch=commit_id,
                path=str(file_meta),
            )
            if file_meta.suffix == JSON_SUFFIX:
                properties[key] = json.loads(file_content.decode("utf-8"))
            else:
                properties[key] = file_content
        else:
            properties[key] = value
    return Entity(
        **{
            **raw_entity.dict(exclude_unset=True),
            "properties": properties,
        }
    )


async def generate_entities_from_yaml_file(
    file_content: str,
    client: BitbucketClient,
    commit_id: str,
    repository_id: str,
    file_name: str,
) -> list[Entity]:
    try:
        loaded_yaml = yaml.safe_load(file_content)
        logger.debug(f"Loaded YAML: {loaded_yaml}")
        raw_entities = [
            Entity(**entity_data)
            for entity_data in (
                loaded_yaml if isinstance(loaded_yaml, list) else [loaded_yaml]
            )
        ]
        logger.debug(f"Raw entities: {raw_entities}")
        return [
            await _generate_entity_from_port_yaml(
                entity_data, client, commit_id, repository_id
            )
            for entity_data in raw_entities
        ]
    except Exception as e:
        logger.info(f"Failed to get gitops entities file {file_name} - {str(e)}")
    return []
