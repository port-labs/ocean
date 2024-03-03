import asyncio
import functools
from asyncio import TaskGroup
from functools import lru_cache
from typing import Any

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
    async def _compile(self, pattern: str) -> Any:
        loop = asyncio.get_event_loop()
        compiler = functools.partial(jq.compile, pattern)
        return await loop.run_in_executor(None, compiler)

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        try:
            loop = asyncio.get_event_loop()
            compiled_pattern = await self._compile(pattern)
            first_value_callable = functools.partial(compiled_pattern.first, data)
            return await loop.run_in_executor(None, first_value_callable)
        except Exception:
            return None

    async def _search_as_bool(self, data: dict[str, Any], pattern: str) -> bool:
        loop = asyncio.get_event_loop()
        compiled_pattern = await self._compile(pattern)
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
        with TaskGroup() as tg:
            for key, value in obj.items():
                if isinstance(value, dict):
                    search_tasks[key] = tg.create_task(
                        self._search_as_object(data, value)
                    )
                else:
                    search_tasks[key] = tg.create_task(self._search(data, value))

        result: dict[str, Any | None] = {}
        for key, task in search_tasks.items():
            try:
                result[key] = await task
            except Exception:
                result[key] = None

        return result

    async def _calculate_entities(
        self, mapping: ResourceConfig, raw_data: list[dict[str, Any]]
    ) -> list[Entity]:
        async def calculate_raw(data: dict[str, Any]) -> Entity:
            should_run = await self._search_as_bool(data, mapping.selector.query)
            if should_run and mapping.port.entity:
                return Entity.parse_obj(
                    await self._search_as_object(
                        data, mapping.port.entity.mappings.dict(exclude_unset=True)
                    )
                )

        entities_tasks = [asyncio.create_task(calculate_raw(data)) for data in raw_data]
        entities = asyncio.gather(*entities_tasks)

        return [
            Entity.parse_obj(entity_data)
            for entity_data in filter(
                lambda entity: entity.get("identifier") and entity.get("blueprint"),
                entities,
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
