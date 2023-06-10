from typing import List, Tuple

import jq  # type: ignore

from port_ocean.models.diff import Change
from port_ocean.core.manipulation.base import BaseManipulation, Entity, EntitiesDiff
from port_ocean.core.utils import get_unique_entities
from port_ocean.models.port import Blueprint
from port_ocean.models.port_app_config import ResourceConfig


class JQManipulation(BaseManipulation):
    def _search(self, data: dict, pattern: str):
        try:
            return jq.first(pattern, data) or None
        except:
            return None

    def _search_as_bool(self, data: dict, pattern: str) -> bool:
        value = self._search(data, pattern)

        if isinstance(value, bool):
            return value

        raise Exception(f"Expected boolean value, got {type(value)} instead")

    def _search_as_object(self, data: dict, obj: dict) -> dict:
        result = {}
        for key, value in obj.items():
            try:
                if isinstance(value, dict):
                    result[key] = self._search_as_object(data, value)
                else:
                    result[key] = self._search(data, value)
            except:
                result[key] = None
        return result

    def _create_jq_entities(
        self, mapping: ResourceConfig, raw_data: List[dict]
    ) -> Tuple[List[Entity], List[Blueprint]]:
        entities = []
        blueprints = []
        for data in raw_data:
            should_run = self._search_as_bool(data, mapping.selector.query)

            if should_run:
                if mapping.port.entity:
                    entities.append(
                        self._search_as_object(
                            data, mapping.port.entity.mappings.dict()
                        )
                    )
                if mapping.port.blueprint:
                    blueprints.append(
                        self._search_as_object(
                            data, mapping.port.blueprint.mappings.dict()
                        )
                    )

        return (
            [
                Entity(**entity_data)
                for entity_data in filter(
                    lambda entity: entity.get("identifier") and entity.get("blueprint"),
                    entities,
                )
            ],
            [
                Blueprint(**blueprint_data)
                for blueprint_data in filter(
                    lambda blueprint: blueprint.get("identifier"), blueprints
                )
            ],
        )

    def get_entities_diff(
        self, mapping: ResourceConfig, raw_results: List[Change]
    ) -> EntitiesDiff:
        entities_before, blueprints_before, entities_after, blueprints_after = zip(
            *[
                (
                    *self._create_jq_entities(mapping, result["before"]),
                    *self._create_jq_entities(mapping, result["after"]),
                )
                for result in raw_results
            ]
        )

        return EntitiesDiff(
            deleted=get_unique_entities(
                [
                    entity
                    for entity in entities_before
                    if not any(
                        entity == entity_after for entity_after in entities_after
                    )
                ]
            ),
            created=get_unique_entities(
                [
                    entity
                    for entity in entities_after
                    if not any(
                        entity == entity_before for entity_before in entities_before
                    )
                ]
            ),
            modified=get_unique_entities(
                [
                    entity
                    for entity in entities_after
                    if any(entity == entity_before for entity_before in entities_before)
                ]
            ),
        )
