from graphlib import TopologicalSorter, CycleError
from typing import Set

from port_ocean.core.models import Entity
from port_ocean.exceptions.core import OceanAbortException

Node = tuple[str, str]


def node(entity: Entity) -> Node:
    return entity.identifier, entity.blueprint


def order_by_entities_dependencies(entities: list[Entity]) -> list[Entity]:
    nodes: dict[Node, Set[Node]] = {}
    entities_map = {}
    for entity in entities:
        nodes[node(entity)] = set()
        entities_map[node(entity)] = entity

    for entity in entities:
        relation_target_ids: list[str] = sum(
            [
                identifiers if isinstance(identifiers, list) else [identifiers]
                for identifiers in entity.relations.values()
                if identifiers is not None
            ],
            [],
        )
        related_entities = [
            related for related in entities if related.identifier in relation_target_ids
        ]

        for related_entity in related_entities:
            if (
                entity.blueprint is not related_entity.blueprint
                or entity.identifier is not related_entity.identifier
            ):
                nodes[node(entity)].add(node(related_entity))

    sort_op = TopologicalSorter(nodes)
    try:
        return [entities_map[item] for item in sort_op.static_order()]
    except CycleError as ex:
        raise OceanAbortException(
            "Cannot order entities due to cyclic dependencies. \n"
            "If you do want to have cyclic dependencies, please make sure to set the keys"
            " 'createMissingRelatedEntities' and 'deleteDependentEntities' in the integration config in Port."
        ) from ex
