import asyncio
from itertools import groupby

from port_ocean.clients.port.client import PortClient
from port_ocean.core.models import Entity


async def get_related_entities(
    entities: list[Entity], port_client: PortClient
) -> list[Entity]:
    entities_with_relations = [entity for entity in entities if entity.relations]
    blueprint_identifier_to_entity = dict(
        groupby(
            entities_with_relations,
            key=lambda x: x.blueprint,
        )
    )
    blueprints = await asyncio.gather(
        *(
            port_client.get_blueprint(blueprint_identifier)
            for blueprint_identifier in blueprint_identifier_to_entity.keys()
        )
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

    related_entities = []
    for entity, blueprint in entity_to_blueprint:
        for relation_name, relation in entity.relations.items():
            relation_blueprint = blueprint.relations[relation_name].target
            related_entities.append(
                Entity(identifier=relation, blueprint=relation_blueprint)
            )

    return related_entities
