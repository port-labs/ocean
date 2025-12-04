from typing import Any, Generator
from port_ocean.context import event
from port_ocean.core.models import Entity

from loguru import logger

from graphlib import TopologicalSorter, CycleError
from typing import Set

from port_ocean.exceptions.core import OceanAbortException

Node = tuple[str, str]


class EntityTopologicalSorter:
    def __init__(self) -> None:
        self.entities: list[Entity] = []

    def register_entity(
        self,
        entity: Entity,
    ) -> None:
        logger.debug(
            f"Will retry upserting entity - {entity.identifier} at the end of resync"
        )
        self.entities.append(entity)

    def should_execute(self) -> int:
        return not event.event.port_app_config.create_missing_related_entities

    def get_entities_count(self) -> int:
        return len(self.entities)

    def get_entities(self, sorted: bool = True) -> Generator[Entity, Any, None]:
        if not sorted:
            for entity in self.entities:
                yield entity
            return

        sorted_and_mapped = EntityTopologicalSorter.order_by_entities_dependencies(
            self.entities
        )
        for entity in sorted_and_mapped:
            yield entity

    @staticmethod
    def node(entity: Entity) -> Node:
        return entity.identifier, entity.blueprint

    @staticmethod
    def order_by_entities_dependencies(entities: list[Entity]) -> list[Entity]:
        nodes: dict[Node, Set[Node]] = {}
        entities_map = {}
        for entity in entities:
            nodes[EntityTopologicalSorter.node(entity)] = set()
            entities_map[EntityTopologicalSorter.node(entity)] = entity

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
                related
                for related in entities
                if related.identifier in relation_target_ids
            ]

            for related_entity in related_entities:
                if (
                    entity.blueprint is not related_entity.blueprint
                    or entity.identifier is not related_entity.identifier
                ):
                    nodes[EntityTopologicalSorter.node(entity)].add(
                        EntityTopologicalSorter.node(related_entity)
                    )

        sort_op = TopologicalSorter(nodes)
        try:
            return [entities_map[item] for item in sort_op.static_order()]
        except CycleError as ex:
            raise OceanAbortException(
                "Cannot order entities due to cyclic dependencies. \n"
                "If you do want to have cyclic dependencies, please make sure to set the keys"
                " 'createMissingRelatedEntities' and 'deleteDependentEntities' in the integration config in Port."
            ) from ex
