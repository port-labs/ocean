from graphlib import TopologicalSorter
from typing import List, Dict, Tuple, Set

from port_ocean.core.handlers.manipulation.base import (
    PortDiff,
    PortObjectDiff,
    flatten_diff,
    Entity,
    Blueprint,
)
from port_ocean.core.handlers.transport.base import BaseTransport

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


class HttpPortTransport(BaseTransport):
    async def _update_entity_diff(self, diff: PortObjectDiff[Entity]) -> None:
        ordered_deleted_entities = order_by_entities_dependencies(diff.deleted)
        for entity in ordered_deleted_entities:
            await self.context.port_client.delete_entity(entity)

        ordered_created_entities = reversed(
            order_by_entities_dependencies(diff.created)
        )
        for entity in ordered_created_entities:
            await self.context.port_client.upsert_entity(entity)

        ordered_modified_entities = reversed(
            order_by_entities_dependencies(diff.modified)
        )
        for entity in ordered_modified_entities:
            await self.context.port_client.upsert_entity(entity)

    async def update_diff(self, changes: List[PortDiff]) -> None:
        entities: PortObjectDiff[Entity] = flatten_diff(
            [change[0] for change in changes]
        )
        blueprints: PortObjectDiff[Blueprint] = flatten_diff(
            [change[1] for change in changes]
        )

        await self._update_entity_diff(entities)
