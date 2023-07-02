from port_ocean.core.models import Entity, Blueprint
from port_ocean.core.utils import is_same_entity
from port_ocean.exceptions.base import RelationValidationException


def get_required_entities(
    entity_to_blueprint: list[tuple[Entity, Blueprint]],
    forbidden_entities: list[Entity],
    excluded_entities: list[Entity],
) -> list[Entity]:
    required_entities = []
    for entity, blueprint in entity_to_blueprint:
        for relation_name, relation in entity.relations.items():
            relation_blueprint = blueprint.relations[relation_name].target
            target_entity = Entity(identifier=relation, blueprint=relation_blueprint)

            if any(is_same_entity(item, target_entity) for item in forbidden_entities):
                raise RelationValidationException(
                    f"Cant delete entity {target_entity} of blueprint {target_entity.blueprint} "
                    f"because it was specified as relation target of entity {entity} "
                    f"of blueprint {entity.blueprint}"
                )

            if not any(
                is_same_entity(item, target_entity) for item in excluded_entities
            ):
                required_entities.append(target_entity)

    return required_entities
