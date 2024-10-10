import asyncio
from collections import defaultdict
from itertools import groupby

from port_ocean.clients.port.client import PortClient
from port_ocean.core.models import EntityRef


async def get_related_entities_refs(
    entity_refs: list[EntityRef], port_client: PortClient
) -> list[EntityRef]:
    entities_with_relations = [entity for entity in entity_refs if entity.relations]
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

    blueprints_to_relations = defaultdict(list)
    for entity, blueprint in entity_to_blueprint:
        for relation_name, relation in entity.relations.items():
            relation_blueprint = blueprint.relations[relation_name].target
            blueprints_to_relations[relation_blueprint].extend(
                relation if isinstance(relation, list) else [relation]
            )

    return [
        EntityRef(identifier=relation, blueprint=blueprint)
        for blueprint, relations in blueprints_to_relations.items()
        # multiple entities can point to the same relation in the same blueprint, for performance reasons
        # we want to avoid fetching the same relation multiple times
        for relation in set(relations)
    ]
