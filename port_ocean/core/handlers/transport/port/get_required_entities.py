from typing import List, Tuple

from port_ocean.core.models import Entity, Blueprint
from port_ocean.core.utils import is_same_entity


def get_required_entities(
    entity_to_blueprint: List[Tuple[Entity, Blueprint]],
    forbidden_entities: List[Entity],
    excluded_entities: List[Entity],
) -> List[Entity]:
    required_entities = []
    for entity, blueprint in entity_to_blueprint:
        for relation_name, relation in entity.relations.items():
            relation_blueprint = blueprint.relations[relation_name]
            target_entity = Entity(identifier=relation, blueprint=relation_blueprint)

            if any(is_same_entity(item, target_entity) for item in forbidden_entities):
                raise Exception(
                    f"Cant delete entity {target_entity} of blueprint {target_entity.blueprint} "
                    f"because it was specified as relation target of entity {entity} "
                    f"of blueprint {entity.blueprint}"
                )

            if not any(
                is_same_entity(item, target_entity) for item in excluded_entities
            ):
                required_entities.append(target_entity)

    return required_entities
