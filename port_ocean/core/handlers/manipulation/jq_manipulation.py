from typing import List, Tuple, Dict, Any

import jq  # type: ignore

from port_ocean.core.handlers.manipulation.base import (
    BaseManipulation,
    PortDiff,
)
from port_ocean.core.models import Entity, Blueprint
from port_ocean.core.utils import (
    is_same_entity,
    get_object_diff,
    is_same_blueprint,
)
from port_ocean.types import ObjectDiff
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class JQManipulation(BaseManipulation):
    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        try:
            return jq.first(pattern, data) or None
        except Exception:
            return None

    def _search_as_bool(self, data: Dict[str, Any], pattern: str) -> bool:
        value = self._search(data, pattern)

        if isinstance(value, bool):
            return value

        raise Exception(f"Expected boolean value, got {type(value)} instead")

    def _search_as_object(
        self, data: Dict[str, Any], obj: Dict[str, Any]
    ) -> Dict[str, Any | None]:
        result: Dict[str, Any | None] = {}
        for key, value in obj.items():
            try:
                if isinstance(value, dict):
                    result[key] = self._search_as_object(data, value)
                else:
                    result[key] = self._search(data, value)
            except Exception:
                result[key] = None
        return result

    def _parse_items(
        self, mapping: ResourceConfig, raw_data: List[Dict[str, Any]]
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
                Entity.parse_obj(entity_data)
                for entity_data in filter(
                    lambda entity: entity.get("identifier") and entity.get("blueprint"),
                    entities,
                )
            ],
            [
                Blueprint.parse_obj(blueprint_data)
                for blueprint_data in filter(
                    lambda blueprint: blueprint.get("identifier"), blueprints
                )
            ],
        )

    async def get_diff(
        self, mapping: ResourceConfig, raw_results: List[ObjectDiff]
    ) -> PortDiff:
        parsed_results = [
            (
                *self._parse_items(mapping, result["before"]),
                *self._parse_items(mapping, result["after"]),
            )
            for result in raw_results
        ]
        entities_before, blueprints_before, entities_after, blueprints_after = tuple(  # type: ignore
            sum(items, []) for items in zip(*parsed_results)
        )

        entities_diff = get_object_diff(entities_before, entities_after, is_same_entity)
        blueprints_diff = get_object_diff(
            blueprints_before, blueprints_after, is_same_blueprint
        )

        return entities_diff, blueprints_diff
