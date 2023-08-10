from graphlib import TopologicalSorter
from typing import Set

from port_ocean.core.models import Entity

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
            nodes[node(entity)].add(node(related_entity))

    sort_op = TopologicalSorter(nodes)
    return [entities_map[item] for item in sort_op.static_order()]
