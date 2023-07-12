import asyncio

from port_ocean.clients.port.client import PortClient
from port_ocean.core.handlers.entities_state_applier.port.get_related_entities import (
    get_related_entities,
)
from port_ocean.core.handlers.entity_processor.base import EntityPortDiff
from port_ocean.core.utils import is_same_entity
from port_ocean.exceptions.core import RelationValidationException


async def validate_entity_relations(
    diff: EntityPortDiff, port_client: PortClient
) -> None:
    modified_or_created_entities = diff.modified + diff.created
    related_entities = await get_related_entities(
        modified_or_created_entities, port_client
    )

    required_entities = []

    for entity in related_entities:
        if any(is_same_entity(item, entity) for item in diff.deleted):
            raise RelationValidationException(
                f"Cant delete entity {entity} of blueprint {entity.blueprint} "
                f"because it was specified as relation target of entity {entity} "
                f"of blueprint {entity.blueprint}"
            )

        if not any(
            is_same_entity(item, entity) for item in modified_or_created_entities
        ):
            required_entities.append(entity)

    await asyncio.gather(
        *(
            port_client.validate_entity_exist(item.identifier, item.blueprint)
            for item in required_entities
        )
    )
