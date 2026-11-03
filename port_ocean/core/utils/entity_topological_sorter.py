from graphlib import TopologicalSorter, CycleError

from port_ocean.core.models import Entity
from port_ocean.core.utils.entity_identifier import (
    normalize_identifier,
    relation_target_identifier_keys,
)
from port_ocean.exceptions.core import OceanAbortException

Node = tuple[str, str]


def _node(entity: Entity) -> Node:
    return (
        normalize_identifier(entity.identifier),
        entity.blueprint,
    )


def order_by_entities_dependencies(entities: list[Entity]) -> list[Entity]:
    nodes: dict[Node, set[Node]] = {}
    entities_map = {}
    for entity in entities:
        nodes[_node(entity)] = set()
        entities_map[_node(entity)] = entity

    for entity in entities:
        relation_target_ids: set[str] = set()
        for identifiers in entity.relations.values():
            if identifiers is None:
                continue
            for identifier in (
                identifiers if isinstance(identifiers, list) else [identifiers]
            ):
                relation_target_ids.update(relation_target_identifier_keys(identifier))

        related_entities = [
            related
            for related in entities
            if normalize_identifier(related.identifier) in relation_target_ids
        ]

        for related_entity in related_entities:
            if _node(entity) != _node(related_entity):
                nodes[_node(entity)].add(_node(related_entity))

    sort_op = TopologicalSorter(nodes)
    try:
        return [entities_map[item] for item in sort_op.static_order()]
    except CycleError as ex:
        raise OceanAbortException(
            "Cannot order entities due to cyclic dependencies. \n"
            "If you do want to have cyclic dependencies, please make sure to set the keys"
            " 'createMissingRelatedEntities' and 'deleteDependentEntities' in the integration config in Port."
        ) from ex
