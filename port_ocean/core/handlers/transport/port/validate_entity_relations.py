import asyncio
from itertools import groupby

from port_ocean.clients.port.client import PortClient
from port_ocean.core.handlers.manipulation.base import PortObjectDiff, Entity
from port_ocean.core.handlers.transport.port.get_required_entities import (
    get_required_entities,
)


async def validate_entity_relations(
    diff: PortObjectDiff[Entity], port_client: PortClient
) -> None:
    modified_or_created_entities = diff.modified + diff.created
    entities_with_relations = [
        entity for entity in modified_or_created_entities if entity.relations
    ]
    blueprint_identifier_to_entity = dict(
        groupby(
            entities_with_relations,
            key=lambda x: x.blueprint,
        )
    )
    blueprints = await asyncio.gather(
        *[
            port_client.get_blueprint(blueprint_identifier)
            for blueprint_identifier in blueprint_identifier_to_entity.keys()
        ]
    )
    entity_to_blueprint = [
        (
            entity,
            next(
                blueprint
                for blueprint in blueprints
                if blueprint.identifier == entity.blueprint
            ),
        )
        for entity in entities_with_relations
    ]

    required_entities = get_required_entities(
        entity_to_blueprint, diff.deleted, modified_or_created_entities
    )

    await asyncio.gather(
        *[
            port_client.validate_entity_exist(item.identifier, item.blueprint)
            for item in required_entities
        ]
    )
