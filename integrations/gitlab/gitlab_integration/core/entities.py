import json
from pathlib import Path

from gitlab.v4.objects import Project

from port_ocean.core.models import Entity

from gitlab_integration.core.async_fetcher import AsyncFetcher

FILE_PROPERTY_PREFIX = "file://"
SEARCH_PROPERTY_PREFIX = "search://"
JSON_SUFFIX = ".json"


async def generate_entity_from_port_yaml(
    raw_entity: Entity, project: Project, ref: str
) -> Entity:
    properties = {}
    for key, value in raw_entity.properties.items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
            gitlab_file = await AsyncFetcher.fetch_single(
                project.files.get, str(file_meta), ref
            )

            if file_meta.suffix == JSON_SUFFIX:
                properties[key] = json.loads(gitlab_file.decode().decode("utf-8"))
            else:
                properties[key] = gitlab_file.decode().decode("utf-8")
        else:
            properties[key] = value

    return Entity(
        **{
            **raw_entity.dict(exclude_unset=True),
            "properties": properties,
        }
    )
