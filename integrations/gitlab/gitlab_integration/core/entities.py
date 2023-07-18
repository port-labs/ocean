import json
from pathlib import Path

from gitlab import Gitlab

from gitlab_integration.models import HookContext
from port_ocean.core.models import Entity

FILE_PROPERTY_PREFIX = "file://"
JSON_SUFFIX = ".json"


def generate_entity_from_port_yaml(
    raw_entity: Entity, context: HookContext, gitlab_client: Gitlab, ref: str
) -> Entity:
    properties = {}
    for key, value in raw_entity.properties.items():
        if isinstance(value, str) and value.startswith(FILE_PROPERTY_PREFIX):
            file_meta = Path(value.replace(FILE_PROPERTY_PREFIX, ""))
            gitlab_file = gitlab_client.projects.get(context.project.id).files.get(
                file_path=str(file_meta), ref=ref
            )

            if file_meta.suffix == JSON_SUFFIX:
                properties[key] = json.loads(gitlab_file.decode())
            else:
                properties[key] = gitlab_file.decode()
        else:
            properties[key] = value

    return Entity(
        **raw_entity.dict(exclude_unset=True),
        properties=properties,
    )
