from typing import Any, Generator
from port_ocean.core.models import Entity
from port_ocean.core.handlers.entities_state_applier.port.order_by_entities_dependencies import (
    order_by_entities_dependencies,
)

from dataclasses import dataclass, field
from loguru import logger


@dataclass
class EntityTopologicalSorter:
    entities: list[Entity] = field(default_factory=list)

    def register_entity(
        self,
        entity: Entity,
    ) -> None:
        logger.debug(
            f"Will retry upserting entity - {entity.identifier} at the end of resync"
        )
        self.entities.append(entity)

    @staticmethod
    def order_by_entities_dependencies(entities: list[Entity]) -> list[Entity]:
        return order_by_entities_dependencies(entities)

    def get_entities(self) -> Generator[Entity, Any, None]:
        entity_map: dict[str, Entity] = {
            f"{entity.identifier}-{entity.blueprint}": entity
            for entity in self.entities
        }
        sorted_and_mapped = order_by_entities_dependencies(self.entities)
        for obj in sorted_and_mapped:
            entity = entity_map.get(f"{obj.identifier}-{obj.blueprint}")
            if entity is not None:
                yield entity
