from typing import Any, AsyncGenerator, Optional
from loguru import logger
import yaml
from client import BitbucketClient
from integration import BitbucketAppConfig
from port_ocean.core.handlers.webhook.webhook_event import EventPayload
from port_ocean.core.models import Entity
from pydantic import BaseModel, ValidationError


class PortEntity(BaseModel):
    identifier: str
    title: str
    blueprint: str
    properties: dict[str, Any]
    relations: dict[str, Any]


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


async def generate_entities_from_commit_id(
    bitbucket_client: BitbucketClient,
    file_name: str,
    repository_id: str,
    commit_id: str,
) -> list[Entity]:
    try:
        logger.debug(
            f"Generating entities for commit {commit_id} in repository {repository_id}"
        )
        file_content = await bitbucket_client.get_file_content(
            repository_id, commit_id, file_name
        )
        if not file_content:
            logger.warning(
                f"No file content found for {file_name} at commit {commit_id}"
            )
            return []

        # Parse the file content into entities
        from port_ocean.core.handlers import JQEntityProcessor
        from port_ocean.context.event import event

        processor = JQEntityProcessor(event.context)
        entities = await processor.process_raw([{"content": file_content}])

        logger.debug(f"Generated {len(entities)} entities from commit {commit_id}")
        return entities

    except Exception as e:
        logger.error(f"Error generating entities from commit {commit_id}: {e}")
        return []


def validate_port_yaml(data: dict):
    try:
        data["properties"] = data.get("properties") or {}
        data["relations"] = data.get("relations") or {}
        validated_entity = PortEntity(**data)
        return validated_entity.model_dump()
    except ValidationError as e:
        logger.error(f"Validation error for entity: {e.json()}")
        return None
    except Exception as e:
        logger.error(f"Error validating entity: {e}")
        return None


async def generate_entities_from_yaml_file(
    file_content: str,
) -> Optional[list[Entity]]:
    try:
        loaded_yaml = yaml.safe_load(file_content)
        if loaded_yaml:
            logger.info(f"Creating entity from port.yaml: {loaded_yaml}")
        if isinstance(loaded_yaml, dict):
            validated_entity = validate_port_yaml(loaded_yaml)
            return validated_entity
        elif isinstance(loaded_yaml, list):
            entities = []
            for entity in loaded_yaml:
                validated_entity = validate_port_yaml(entity)
                if validated_entity:
                    entities.append(validated_entity)
                else:
                    logger.error(f"Invalid entity schema: {entity}")
            return entities
        else:
            logger.error(
                f"Invalid entity port.yaml schema : {loaded_yaml} with type {type(loaded_yaml)}"
            )
            return None
    except Exception as e:
        logger.error(f"Error parsing YAML file: {e}")
        return None
