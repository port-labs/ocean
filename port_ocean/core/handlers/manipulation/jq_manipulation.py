from functools import lru_cache
from typing import List, Dict, Any

import pyjq as jq  # type: ignore

from port_ocean.core.handlers.manipulation.base import BaseManipulation
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.types import EntityRawDiff, EntityDiff


class JQManipulation(BaseManipulation):
    @lru_cache
    def _compile(self, pattern: str) -> Any:
        return jq.compile(pattern)

    def _search(self, data: Dict[str, Any], pattern: str) -> Any:
        try:
            return self._compile(pattern).first(data) or None
        except Exception:
            return None

    def _search_as_bool(self, data: Dict[str, Any], pattern: str) -> bool:
        value = self._compile(pattern).first(data)

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
    ) -> List[Entity]:
        entities = []
        for data in raw_data:
            should_run = self._search_as_bool(data, mapping.selector.query)

            if should_run:
                if mapping.port.entity:
                    entities.append(
                        self._search_as_object(
                            data, mapping.port.entity.mappings.dict()
                        )
                    )

        return [
            Entity.parse_obj(entity_data)
            for entity_data in filter(
                lambda entity: entity.get("identifier") and entity.get("blueprint"),
                entities,
            )
        ]

    async def parse_items(
        self, mapping: ResourceConfig, raw_results: List[EntityRawDiff]
    ) -> EntityDiff:
        parsed_results = [
            (
                self._parse_items(mapping, result["before"]),
                self._parse_items(mapping, result["after"]),
            )
            for result in raw_results
        ]
        entities_before, entities_after = [], []

        if parsed_results:
            entities_before, entities_after = tuple(
                (sum(items, []) for items in zip(*parsed_results))
            )

        entities_diff: EntityDiff = {
            "before": entities_before,
            "after": entities_after,
        }

        return entities_diff
