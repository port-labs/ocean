from typing import List, Set

from framework.models.port import Entity


def is_same_entity(firs_entity: Entity, second_entity: Entity) -> bool:
    return firs_entity.identifier == second_entity.identifier and firs_entity.blueprint == second_entity.blueprint


def get_unique_entities(array: List[Entity]):
    seen: Set[Entity] = set()
    result = []
    for item in array:
        if all(not is_same_entity(item, seen_item) for seen_item in seen):
            seen.add(item)
            result.append(item)
    return result
