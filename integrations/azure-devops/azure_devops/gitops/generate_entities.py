import json
from pathlib import Path
from typing import Any, List

import yaml
from loguru import logger
from port_ocean.core.models import Entity
from yaml.parser import ParserError

from azure_devops.client.azure_devops_client import AzureDevopsClient

from .file_entity_processor import FILE_PROPERTY_PREFIX

JSON_SUFFIX = ".json"


async def _generate_entity_from_port_yaml(
    azure_devops_client: AzureDevopsClient,
    raw_entity: Entity,
    commit_id: str,
    repository_id: str,
) -> dict[str, Any]:
    properties = {}
    for key, value in raw_entity.properties.items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
            file_content: bytes = await azure_devops_client.get_file_by_commit(
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

    return {
        **raw_entity.dict(exclude_unset=True),
        "properties": properties,
    }


async def _generate_entities_from_port_yaml(
    azure_devops_client: AzureDevopsClient,
    file_name: str,
    repository_id: str,
    commit_id: str,
) -> List[dict[str, Any]]:
    try:
        file_content = await azure_devops_client.get_file_by_commit(
            file_name, repository_id, commit_id
        )
        entities = yaml.safe_load(file_content.decode())
        raw_entities = [
            Entity(**entity_data)
            for entity_data in (entities if isinstance(entities, list) else [entities])
        ]
        return [
            await _generate_entity_from_port_yaml(
                azure_devops_client, entity_data, commit_id, repository_id
            )
            for entity_data in raw_entities
        ]
    except ParserError as e:
        logger.info(f"Failed to parse gitops entities file {file_name} - {str(e)}")
    except Exception as e:
        logger.info(f"Failed to get gitops entities file {file_name} - {str(e)}")
    return []


async def generate_entities_from_commit_id(
    azure_devops_client: AzureDevopsClient,
    spec_paths: list[str] | str,
    commit_id: str,
    repository_id: str,
) -> List[dict[str, Any]]:
    if isinstance(spec_paths, str):
        spec_paths = [spec_paths]

    return [
        entity
        for path in spec_paths
        for entity in (
            await _generate_entities_from_port_yaml(
                azure_devops_client, path, repository_id, commit_id
            )
        )
    ]
