import json
from pathlib import Path
import yaml
from yaml.parser import ParserError
from port_ocean.core.models import Entity
from .file_entity_processor import FILE_PROPERTY_PREFIX
from azure_devops.client import AzureDevopsHTTPClient
from loguru import logger

JSON_SUFFIX = ".json"


def _generate_entity_from_port_yaml(
    raw_entity: Entity,
    azure_devops_client: AzureDevopsHTTPClient,
    commit_id: str,
    repository_id: str,
) -> Entity:
    properties = {}
    for key, value in raw_entity.properties.items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
            file_content: bytes = azure_devops_client.get_file_by_commit(
                file_path=str(file_meta),
                repository_id=repository_id,
                commit_id=commit_id,
            )

            if file_meta.suffix == JSON_SUFFIX:
                properties[key] = json.loads(file_content.decode("utf-8"))
            else:
                properties[key] = file_content.decode("utf-8")
        else:
            properties[key] = value

    return Entity(
        **{
            **raw_entity.dict(exclude_unset=True),
            "properties": properties,
        }
    )


def _generate_entities_from_port_yaml(
    azure_devops_client: AzureDevopsHTTPClient,
    file_name: str,
    repository_id: str,
    commit_id: str,
) -> list[Entity]:
    try:
        file_content = azure_devops_client.get_file_by_commit(
            file_name, repository_id, commit_id
        )
        entities = yaml.safe_load(file_content.decode())
        raw_entities = [
            Entity(**entity_data)
            for entity_data in (entities if isinstance(entities, list) else [entities])
        ]
        return [
            _generate_entity_from_port_yaml(
                entity_data, azure_devops_client, commit_id, repository_id
            )
            for entity_data in raw_entities
        ]
    except ParserError as e:
        logger.error(f"Failed to parse gitops entities file {file_name} - {str(e)}")
    except Exception as e:
        logger.error(f"Failed to get gitops entities file {file_name} - {str(e)}")
    return []


def generate_entities_from_commit_id(
    azure_devops_client: AzureDevopsHTTPClient,
    spec_paths: list[str],
    repo_id: str,
    commit_id: str,
) -> list[Entity]:
    return [
        entity
        for path in spec_paths
        for entity in _generate_entities_from_port_yaml(
            azure_devops_client, path, repo_id, commit_id
        )
    ]
