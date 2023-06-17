from graphlib import TopologicalSorter
from typing import List, Dict, Set, Tuple

from port_ocean.core.models import Entity

Node = Tuple[str, str]


def order_by_entities_dependencies(entities: List[Entity]) -> List[Entity]:
    nodes: Dict[Node, Set[Node]] = {}
    entities_map = {}

    for entity in entities:
        nodes[(entity.identifier, entity.blueprint)] = set()
        entities_map[(entity.identifier, entity.blueprint)] = entity

    for entity in entities:
        relation_target_ids = [
            identifier
            for relation in entity.relations.values()
            for identifier in relation
        ]
        related_entities = [
            related for related in entities if related.identifier in relation_target_ids
        ]

        for related_entity in related_entities:
            nodes[(entity.identifier, entity.blueprint)].add(
                (related_entity.identifier, related_entity.blueprint)
            )

    sort_op = TopologicalSorter(nodes)
    return [entities_map[item] for item in sort_op.static_order()]
