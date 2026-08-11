from port_ocean.core.models import Entity
from port_ocean.core.utils.entity_topological_sorter import EntityTopologicalSorter

Node = tuple[object, str]


def node(entity: Entity) -> Node:
    return EntityTopologicalSorter.node(entity)


def order_by_entities_dependencies(entities: list[Entity]) -> list[Entity]:
    return EntityTopologicalSorter.order_by_entities_dependencies(entities)
