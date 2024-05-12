import asyncio
import functools
from functools import lru_cache
from typing import Any
from loguru import logger

import pyjq as jq  # type: ignore

from port_ocean.core.handlers.entity_processor.base import BaseEntityProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    EntitySelectorDiff,
)
from port_ocean.exceptions.core import EntityProcessorException
from port_ocean.utils.queue_utils import process_in_queue


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

    async def _get_mapped_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        selector_query: str,
        parse_all: bool = False,
    ) -> tuple[dict[str, Any], bool]:
        should_run = await self._search_as_bool(data, selector_query)
        if parse_all or should_run:
            mapped_entity = await self._search_as_object(data, raw_entity_mappings)
            return mapped_entity, should_run

        return {}, False

    async def _calculate_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        items_to_parse: str | None,
        selector_query: str,
        parse_all: bool = False,
    ) -> list[tuple[dict[str, Any], bool]]:
        if items_to_parse:
            items = await self._search(data, items_to_parse)
            if isinstance(items, list):
                return await asyncio.gather(
                    *[
                        self._get_mapped_entity(
                            {"item": item, **data},
                            raw_entity_mappings,
                            selector_query,
                            parse_all,
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
                await self._get_mapped_entity(
                    data, raw_entity_mappings, selector_query, parse_all
                )
            ]
        return [({}, False)]

    async def _parse_items(
        self,
        mapping: ResourceConfig,
        raw_results: list[RAW_ITEM],
        parse_all: bool = False,
    ) -> EntitySelectorDiff:
        raw_entity_mappings: dict[str, Any] = mapping.port.entity.mappings.dict(
            exclude_unset=True
        )

        calculated_entities_results = await process_in_queue(
            raw_results,
            self._calculate_entity,
            raw_entity_mappings,
            mapping.port.items_to_parse,
            mapping.selector.query,
            parse_all,
        )

        passed_entities = []
        failed_entities = []
        for entities_results in calculated_entities_results:
            for entity, did_entity_pass_selector in entities_results:
                if entity.get("identifier") and entity.get("blueprint"):
                    parsed_entity = Entity.parse_obj(entity)
                    if did_entity_pass_selector:
                        passed_entities.append(parsed_entity)
                    else:
                        failed_entities.append(parsed_entity)

        return EntitySelectorDiff(passed=passed_entities, failed=failed_entities)
