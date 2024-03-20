import asyncio
import functools
from functools import lru_cache
from typing import Any
from loguru import logger

import pyjq as jq  # type: ignore

from port_ocean.core.handlers.entity_processor.base import BaseEntityProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import RawEntityDiff, EntityDiff
from port_ocean.exceptions.core import EntityProcessorException


class JQEntityProcessor(BaseEntityProcessor):
    """Processes and parses entities using JQ expressions.

    This class extends the BaseEntityProcessor and provides methods for processing and
    parsing entities based on PyJQ queries. It supports compiling and executing PyJQ patterns,
    searching for data in dictionaries, and transforming data based on object mappings.
    """

    @lru_cache
    def _compile(self, pattern: str) -> Any:
        return jq.compile(pattern)

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        try:
            loop = asyncio.get_event_loop()
            compiled_pattern = self._compile(pattern)
            first_value_callable = functools.partial(compiled_pattern.first, data)
            return await loop.run_in_executor(None, first_value_callable)
        except Exception:
            return None

    async def _search_as_bool(self, data: dict[str, Any], pattern: str) -> bool:
        loop = asyncio.get_event_loop()
        compiled_pattern = self._compile(pattern)
        first_value_callable = functools.partial(compiled_pattern.first, data)
        value = await loop.run_in_executor(None, first_value_callable)

        if isinstance(value, bool):
            return value

        raise EntityProcessorException(
            f"Expected boolean value, got {type(value)} instead"
        )

    async def _search_as_object(
        self, data: dict[str, Any], obj: dict[str, Any]
    ) -> dict[str, Any | None]:
        search_tasks = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                search_tasks[key] = asyncio.create_task(
                    self._search_as_object(data, value)
                )
            else:
                search_tasks[key] = asyncio.create_task(self._search(data, value))

        result: dict[str, Any | None] = {}
        for key, task in search_tasks.items():
            try:
                result[key] = await task
            except Exception:
                result[key] = None

        return result

    async def _get_entity_if_passed_selector(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        selector_query: str,
    ) -> dict[str, Any]:
        should_run = await self._search_as_bool(data, selector_query)
        if should_run:
            return await self._search_as_object(data, raw_entity_mappings)
        return {}

    async def _calculate_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        items_to_parse: str | None,
        selector_query: str,
    ) -> list[dict[str, Any]]:
        if items_to_parse:
            items = await self._search(data, items_to_parse)
            if isinstance(items, list):
                return await asyncio.gather(
                    *[
                        self._get_entity_if_passed_selector(
                            {"item": item, **data},
                            raw_entity_mappings,
                            selector_query,
                        )
                        for item in items
                    ]
                )
            logger.warning(
                f"Failed to parse items for JQ expression {items_to_parse}, Expected list but got {type(items)}."
                f" Skipping..."
            )
        else:
            return [
                await self._get_entity_if_passed_selector(
                    data, raw_entity_mappings, selector_query
                )
            ]
        return [{}]

    async def _calculate_entities(
        self, mapping: ResourceConfig, raw_data: list[dict[str, Any]]
    ) -> list[Entity]:
        raw_entity_mappings: dict[str, Any] = mapping.port.entity.mappings.dict(
            exclude_unset=True
        )
        entities_tasks = [
            asyncio.create_task(
                self._calculate_entity(
                    data,
                    raw_entity_mappings,
                    mapping.port.items_to_parse,
                    mapping.selector.query,
                )
            )
            for data in raw_data
        ]
        entities = await asyncio.gather(*entities_tasks)

        return [
            Entity.parse_obj(entity_data)
            for flatten in entities
            for entity_data in filter(
                lambda entity: entity.get("identifier") and entity.get("blueprint"),
                flatten,
            )
        ]

    async def _parse_items(
        self, mapping: ResourceConfig, raw_results: RawEntityDiff
    ) -> EntityDiff:
        entities_before: list[Entity] = await self._calculate_entities(
            mapping, raw_results["before"]
        )
        entities_after: list[Entity] = await self._calculate_entities(
            mapping, raw_results["after"]
        )

        return {
            "before": entities_before,
            "after": entities_after,
        }
