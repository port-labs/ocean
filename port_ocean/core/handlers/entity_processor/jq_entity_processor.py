import asyncio
from asyncio import Task
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional
import jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.entity_processor.base import BaseEntityProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    EntitySelectorDiff,
    CalculationResult,
)
from port_ocean.core.utils.utils import (
    gather_and_split_errors_from_results,
    zip_and_sum,
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
    misconfigurations: dict[str, str] = field(default_factory=dict)


class JQEntityProcessor(BaseEntityProcessor):
    """Processes and parses entities using JQ expressions.

    This class extends the BaseEntityProcessor and provides methods for processing and
    parsing entities based on PyJQ queries. It supports compiling and executing PyJQ patterns,
    searching for data in dictionaries, and transforming data based on object mappings.
    """

    @lru_cache
    def _compile(self, pattern: str) -> Any:
        if not ocean.config.allow_environment_variables_jq_access:
            pattern = "def env: {}; {} as $ENV | " + pattern
        return jq.compile(pattern)

    @staticmethod
    def _stop_iterator_handler(func: Any) -> Any:
        """
        Wrap the function to handle StopIteration exceptions.
        Prevents StopIteration from stopping the thread and skipping further queue processing.
        """

        def inner() -> Any:
            try:
                return func()
            except StopIteration:
                return None

        return inner

    @staticmethod
    def _notify_mapping_issues(
        entity_misconfigurations: dict[str, str],
        missing_required_fields: bool,
        entity_mapping_fault_counter: int,
    ) -> None:

        if len(entity_misconfigurations) > 0:
            logger.info(
                f"Unable to find valid data for: {entity_misconfigurations} (null, missing, or misconfigured)"
            )
        if missing_required_fields:
            logger.info(
                f"{entity_mapping_fault_counter} transformations of batch failed due to empty, null or missing values"
            )

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        try:
            loop = asyncio.get_event_loop()
            compiled_pattern = self._compile(pattern)
            func = compiled_pattern.input_value(data)
            return await loop.run_in_executor(
                None, self._stop_iterator_handler(func.first)
            )
        except Exception as exc:
            logger.debug(
                f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
            )
            return None

    async def _search_as_bool(self, data: dict[str, Any], pattern: str) -> bool:
        loop = asyncio.get_event_loop()

        compiled_pattern = self._compile(pattern)
        func = compiled_pattern.input_value(data)

        value = await loop.run_in_executor(
            None, self._stop_iterator_handler(func.first)
        )
        if isinstance(value, bool):
            return value
        raise EntityProcessorException(
            f"Expected boolean value, got value:{value} of type: {type(value)} instead"
        )

    async def _search_as_object(
        self,
        data: dict[str, Any],
        obj: dict[str, Any],
        misconfigurations: dict[str, str] | None = None,
    ) -> dict[str, Any | None]:
        """
        Identify and extract the relevant value for the chosen key and populate it into the entity
        :param data: the property itself that holds the key and the value, it is being passed to the task and we get back a task item,
            if the data is a dict, we will recursively call this function again.
        :param obj: the key that we want its value to be mapped into our entity.
        :param misconfigurations: due to the recursive nature of this function,
            we aim to have a dict that represents all of the misconfigured properties and when used recursively,
            we pass this reference to misfoncigured object to add the relevant misconfigured keys.
        :return: Mapped object with found value.
        """

        search_tasks: dict[
            str, Task[dict[str, Any | None]] | list[Task[dict[str, Any | None]]]
        ] = {}
        for key, value in obj.items():
            if isinstance(value, list):
                search_tasks[key] = [
                    asyncio.create_task(
                        self._search_as_object(data, obj, misconfigurations)
                    )
                    for obj in value
                ]

            elif isinstance(value, dict):
                search_tasks[key] = asyncio.create_task(
                    self._search_as_object(data, value, misconfigurations)
                )
            else:
                search_tasks[key] = asyncio.create_task(self._search(data, value))

        result: dict[str, Any | None] = {}
        for key, task in search_tasks.items():
            try:
                if isinstance(task, list):
                    result_list = []
                    for task in task:
                        task_result = await task
                        if task_result is None and misconfigurations is not None:
                            misconfigurations[key] = obj[key]
                        result_list.append(task_result)
                    result[key] = result_list
                else:
                    task_result = await task
                    if task_result is None and misconfigurations is not None:
                        misconfigurations[key] = obj[key]
                    result[key] = task_result
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
            misconfigurations: dict[str, str] = {}
            mapped_entity = await self._search_as_object(
                data, raw_entity_mappings, misconfigurations
            )
            return MappedEntity(
                mapped_entity,
                did_entity_pass_selector=should_run,
                raw_data=data if should_run else None,
                misconfigurations=misconfigurations,
            )

        return MappedEntity()

    async def _calculate_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        items_to_parse: str | None,
        selector_query: str,
        parse_all: bool = False,
    ) -> tuple[list[MappedEntity], list[Exception]]:
        raw_data = [data.copy()]
        if items_to_parse:
            items = await self._search(data, items_to_parse)
            if not isinstance(items, list):
                logger.warning(
                    f"Failed to parse items for JQ expression {items_to_parse}, Expected list but got {type(items)}."
                    f" Skipping..."
                )
                return [], []
            raw_data = [{"item": item, **data} for item in items]

        entities, errors = await gather_and_split_errors_from_results(
            [
                self._get_mapped_entity(
                    raw,
                    raw_entity_mappings,
                    selector_query,
                    parse_all,
                )
                for raw in raw_data
            ]
        )
        if errors:
            logger.error(
                f"Failed to calculate entities with {len(errors)} errors. errors: {errors}"
            )
        return entities, errors

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
    ) -> CalculationResult:
        raw_entity_mappings: dict[str, Any] = mapping.port.entity.mappings.dict(
            exclude_unset=True
        )
        logger.info(f"Parsing {len(raw_results)} raw results into entities")
        calculated_entities_results, errors = zip_and_sum(
            await process_in_queue(
                raw_results,
                self._calculate_entity,
                raw_entity_mappings,
                mapping.port.items_to_parse,
                mapping.selector.query,
                parse_all,
            )
        )
        logger.debug(
            f"Finished parsing raw results into entities with {len(errors)} errors. errors: {errors}"
        )

        passed_entities = []
        failed_entities = []
        examples_to_send: list[dict[str, Any]] = []
        entity_misconfigurations: dict[str, str] = {}
        missing_required_fields: bool = False
        entity_mapping_fault_counter: int = 0

        for result in calculated_entities_results:
            if len(result.misconfigurations) > 0:
                entity_misconfigurations |= result.misconfigurations

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
            else:
                missing_required_fields = True
                entity_mapping_fault_counter += 1

        self._notify_mapping_issues(
            entity_misconfigurations,
            missing_required_fields,
            entity_mapping_fault_counter,
        )

        if (
            not calculated_entities_results
            and raw_results
            and send_raw_data_examples_amount > 0
        ):
            logger.warning(
                f"No entities were parsed from {len(raw_results)} raw results, sending raw data examples"
            )
            examples_to_send = raw_results[:send_raw_data_examples_amount]

        await self._send_examples(examples_to_send, mapping.kind)

        return CalculationResult(
            EntitySelectorDiff(passed=passed_entities, failed=failed_entities),
            errors,
            misonfigured_entity_keys=entity_misconfigurations,
        )
