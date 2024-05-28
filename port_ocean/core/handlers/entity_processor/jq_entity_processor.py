import asyncio
import functools
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

import pyjq as jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.entity_processor.base import BaseEntityProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    EntitySelectorDiff,
)
from port_ocean.exceptions.core import EntityProcessorException
from port_ocean.utils.queue_utils import process_in_queue


@dataclass
class MappedEntity:
    """Represents the entity after applying the mapping

    This class holds the mapping entity along with the selector boolean value and optionally the raw data.
    """

    entity: dict[str, Any] = field(default_factory=dict)
    did_entity_pass_selector: bool = False
    raw_data: Optional[dict[str, Any]] = None


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
    ) -> MappedEntity:
        should_run = await self._search_as_bool(data, selector_query)
        if parse_all or should_run:
            mapped_entity = await self._search_as_object(data, raw_entity_mappings)
            return MappedEntity(
                mapped_entity,
                did_entity_pass_selector=should_run,
                raw_data=data if should_run else None,
            )

        return MappedEntity()

    async def _calculate_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        items_to_parse: str | None,
        selector_query: str,
        parse_all: bool = False,
    ) -> list[MappedEntity]:
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
        return [MappedEntity()]

    @staticmethod
    async def _send_examples(data: list[dict[str, Any]], kind: str) -> None:
        try:
            if data:
                await ocean.port_client.ingest_integration_kind_examples(
                    kind, data, should_log=False
                )
        except Exception as ex:
            logger.warning(
                f"Failed to send raw data example {ex}",
                exc_info=True,
            )

    async def _parse_items(
        self,
        mapping: ResourceConfig,
        raw_results: list[RAW_ITEM],
        parse_all: bool = False,
        send_raw_data_examples_amount: int = 0,
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
        examples_to_send: list[dict[str, Any]] = []
        for entities_results in calculated_entities_results:
            for result in entities_results:
                if result.entity.get("identifier") and result.entity.get("blueprint"):
                    parsed_entity = Entity.parse_obj(result.entity)
                    if result.did_entity_pass_selector:
                        passed_entities.append(parsed_entity)
                        if (
                            len(examples_to_send) < send_raw_data_examples_amount
                            and result.raw_data is not None
                        ):
                            examples_to_send.append(result.raw_data)
                    else:
                        failed_entities.append(parsed_entity)

        await self._send_examples(examples_to_send, mapping.kind)

        return EntitySelectorDiff(passed=passed_entities, failed=failed_entities)
