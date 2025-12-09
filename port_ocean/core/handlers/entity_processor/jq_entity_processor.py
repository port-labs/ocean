import asyncio
from functools import lru_cache
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import re
from asyncio import Task
from dataclasses import dataclass, field
from typing import Any, cast

import jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.entity_processor.base import BaseEntityProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    CalculationResult,
    EntitySelectorDiff,
)
from port_ocean.core.utils.utils import (
    gather_and_split_errors_from_results,
    zip_and_sum,
)
from port_ocean.exceptions.core import EntityProcessorException


@dataclass
class MappedEntity:
    """Represents the entity after applying the mapping

    This class holds the mapping entity along with the selector boolean value and optionally the raw data.
    """

    entity: dict[str, Any] = field(default_factory=dict)
    did_entity_pass_selector: bool = False
    misconfigurations: dict[str, str] = field(default_factory=dict)


# Set globals for multiprocessing of batch data. When a process forks, it inherits these globals by reference.
# We will take advantage of COW to avoid pickling the data.
_MULTIPROCESS_JQ_BATCH_DATA: list[dict[str, Any]] | None = None
_MULTIPROCESS_JQ_BATCH_MAPPINGS: dict[str, Any] | None = None
_MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY: str | None = None
_MULTIPROCESS_JQ_BATCH_PARSE_ALL: bool | None = None

_MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS: dict[str, Any] = {}


def _format_filter(filter: str) -> str:
    formatted_filter = re.sub(r'(^|\s)\'(?!\s|")|(?<!\s|")\'(\s|$)', r'\1"\2', filter)
    return formatted_filter


def _compile(pattern: str) -> Any:
    global _MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS
    # Convert single quotes to double quotes for JQ compatibility
    pattern = _format_filter(pattern)
    if not ocean.config.allow_environment_variables_jq_access:
        pattern = "def env: {}; {} as $ENV | " + pattern
    if pattern in _MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS:
        return _MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS[pattern]
    compiled_pattern = jq.compile(pattern)
    _MULTIPROCESS_JQ_BATCH_COMPILED_PATTERNS[pattern] = compiled_pattern
    return compiled_pattern


def _search_as_bool(data: dict[str, Any] | str, pattern: str) -> bool:
    compiled_pattern = _compile(pattern)
    value = compiled_pattern.input_value(data).first()
    if isinstance(value, bool):
        return value
    raise EntityProcessorException(
        f"Expected boolean value, got value:{value} of type: {type(value)} instead"
    )


def _search(data: dict[str, Any], pattern: str) -> Any:
    try:
        compiled_pattern = _compile(pattern)
        return compiled_pattern.input_value(data).first()
    except Exception as exc:
        logger.error(
            f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
        )
        return None


def _search_as_object(
    data: dict[str, Any],
    obj: dict[str, Any],
    misconfigurations: dict[str, str] | None = None,
) -> dict[str, Any | None]:
    result: dict[str, Any | None | list[Any | None]] = {}
    for key, value in obj.items():
        try:
            if isinstance(value, list):
                result[key] = []
                for list_item in value:
                    search_result = _search_as_object(
                        data, list_item, misconfigurations
                    )
                    cast(list[dict[str, Any | None]], result[key]).append(search_result)
                    if search_result is None and misconfigurations is not None:
                        misconfigurations[key] = obj[key]

            elif isinstance(value, dict):
                search_result = _search_as_object(data, value, misconfigurations)
                result[key] = search_result
                if search_result is None and misconfigurations is not None:
                    misconfigurations[key] = obj[key]

            else:
                search_result = _search(data, value)
                result[key] = search_result
                if search_result is None and misconfigurations is not None:
                    misconfigurations[key] = obj[key]
        except Exception:
            result[key] = None

    return result


def _get_mapped_entity(
    index: int,
    data: dict[str, Any],
    raw_entity_mappings: dict[str, Any],
    selector_query: str,
    parse_all: bool = False,
) -> MappedEntity:
    should_run = _search_as_bool(data, selector_query)
    if parse_all or should_run:
        misconfigurations: dict[str, str] = {}
        mapped_entity = _search_as_object(data, raw_entity_mappings, misconfigurations)
        return MappedEntity(
            mapped_entity,
            did_entity_pass_selector=should_run,
            misconfigurations=misconfigurations,
        )

    return MappedEntity()


def _calculate_entity(
    index: int,
) -> tuple[list[MappedEntity], list[Exception]]:
    # Access data directly from globals to avoid pickling.
    global _MULTIPROCESS_JQ_BATCH_DATA, _MULTIPROCESS_JQ_BATCH_MAPPINGS, _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY, _MULTIPROCESS_JQ_BATCH_PARSE_ALL
    data = (
        _MULTIPROCESS_JQ_BATCH_DATA[index]
        if _MULTIPROCESS_JQ_BATCH_DATA is not None
        else None
    )
    if data is None:
        return [], [Exception(f"Data is missing for index: {index}")]
    raw_entity_mappings = (
        _MULTIPROCESS_JQ_BATCH_MAPPINGS
        if _MULTIPROCESS_JQ_BATCH_MAPPINGS is not None
        else None
    )
    selector_query = (
        _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY
        if _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY is not None
        else None
    )
    parse_all = (
        _MULTIPROCESS_JQ_BATCH_PARSE_ALL
        if _MULTIPROCESS_JQ_BATCH_PARSE_ALL is not None
        else False
    )
    result = _get_mapped_entity(
        index,
        data,
        cast(dict[str, Any], raw_entity_mappings),
        cast(str, selector_query),
        parse_all,
    )
    errors: list[Exception] = []
    entities: list[MappedEntity] = []

    if isinstance(result, BaseException) and not isinstance(result, Exception):
        raise result

    elif isinstance(result, Exception):
        errors.append(result)

    entities.append(result)

    if errors:
        logger.error(
            f"Failed to calculate entities with {len(errors)} errors. errors: {errors}"
        )
    return entities, errors


class JQEntityProcessor(BaseEntityProcessor):
    """Processes and parses entities using JQ expressions.

    This class extends the BaseEntityProcessor and provides methods for processing and
    parsing entities based on PyJQ queries. It supports compiling and executing PyJQ patterns,
    searching for data in dictionaries, and transforming data based on object mappings.
    """

    @staticmethod
    def _format_filter(filter: str) -> str:
        """
        Convert single quotes to double quotes in JQ expressions.
        Only replaces single quotes that are opening or closing string delimiters,
        not single quotes that are part of string content.
        """
        # Escape single quotes only if they are opening or closing a string
        # Pattern matches:
        # - Single quote at start of string or after whitespace (opening quote)
        # - Single quote before whitespace or end of string (closing quote)
        # Uses negative lookahead/lookbehind to avoid replacing quotes inside strings
        # \1 and \2 will be empty for the alternative that didn't match, so \1"\2 works for both cases
        # This matches the TypeScript pattern: /(^|\s)'(?!\s|")|(?<!\s|")'(\s|$)/g
        formatted_filter = re.sub(
            r'(^|\s)\'(?!\s|")|(?<!\s|")\'(\s|$)', r'\1"\2', filter
        )
        return formatted_filter

    @lru_cache
    def _compile(self, pattern: str) -> Any:
        # Convert single quotes to double quotes for JQ compatibility
        pattern = self._format_filter(pattern)
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
            logger.error(
                f"Unable to find valid data for: {entity_misconfigurations} (null, missing, or misconfigured)"
            )
        if missing_required_fields:
            logger.error(
                f"{entity_mapping_fault_counter} transformations of batch failed due to empty, null or missing values"
            )

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        try:
            compiled_pattern = self._compile(pattern)
            func = compiled_pattern.input_value(data)
            return func.first()
        except Exception as exc:
            logger.error(
                f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
            )
            return None

    async def _search_as_bool(self, data: dict[str, Any] | str, pattern: str) -> bool:
        compiled_pattern = self._compile(pattern)
        func = compiled_pattern.input_value(data)
        value = func.first()
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
                misconfigurations=misconfigurations,
            )

        return MappedEntity()

    async def _calculate_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        selector_query: str,
        parse_all: bool = False,
    ) -> tuple[list[MappedEntity], list[Exception]]:
        raw_data = [data.copy()]

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

    def get_patterns(self, raw_entity_mappings: dict[str, Any]) -> list[str]:
        patterns = []
        for key, value in raw_entity_mappings.items():
            if isinstance(value, list):
                for obj in value:
                    patterns.extend(self.get_patterns(obj))
            elif isinstance(value, dict):
                patterns.extend(self.get_patterns(value))
            else:
                patterns.append(value)
        return patterns

    async def warm_up_cache(self, raw_entity_mappings: dict[str, Any]) -> None:
        patterns = self.get_patterns(raw_entity_mappings)
        for pattern in patterns:
            self._compile(pattern)
            await asyncio.sleep(0)

    async def _parse_items(
        self,
        mapping: ResourceConfig,
        raw_results: list[RAW_ITEM],
        parse_all: bool = False,
        send_raw_data_examples_amount: int = 0,
    ) -> CalculationResult:
        # Send raw data examples FIRST (before transformation)
        # This ensures users can see the raw data even if transformation fails
        if send_raw_data_examples_amount > 0 and raw_results:
            examples_to_send = [
                item.copy() for item in raw_results[:send_raw_data_examples_amount]
            ]
            await self._send_examples(examples_to_send, mapping.kind)

        raw_entity_mappings: dict[str, Any] = mapping.port.entity.mappings.dict(
            exclude_unset=True
        )
        logger.info(f"Parsing {len(raw_results)} raw results into entities")
        # Set globals to avoid pickling.
        global _MULTIPROCESS_JQ_BATCH_DATA, _MULTIPROCESS_JQ_BATCH_MAPPINGS, _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY, _MULTIPROCESS_JQ_BATCH_PARSE_ALL
        await self.warm_up_cache(raw_entity_mappings)
        _MULTIPROCESS_JQ_BATCH_DATA = raw_results
        _MULTIPROCESS_JQ_BATCH_MAPPINGS = raw_entity_mappings
        _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = mapping.selector.query
        _MULTIPROCESS_JQ_BATCH_PARSE_ALL = parse_all
        # Fork a new process to calculate the entities.
        # Use indexes to acess data to have the lowest pickling overhead.
        calculated_entities_results: list[MappedEntity] = []
        errors: list[Exception] = []
        pool = ProcessPoolExecutor(
            max_workers=ocean.config.process_in_queue_max_workers,
            mp_context=multiprocessing.get_context("fork"),
        )
        calculated_entities_results, errors = zip_and_sum(
            await asyncio.gather(
                *[
                    asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            pool, _calculate_entity, index
                        ),
                        timeout=10,
                    )
                    for index in range(len(raw_results))
                ],
            )
        )
        pool.shutdown(wait=False)
        del pool
        # Clear globals to avoid memory leaks.
        _MULTIPROCESS_JQ_BATCH_DATA = None
        _MULTIPROCESS_JQ_BATCH_MAPPINGS = None
        _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = None
        _MULTIPROCESS_JQ_BATCH_PARSE_ALL = None

        logger.debug(
            f"Finished parsing raw results into entities with {len(errors)} errors. errors: {errors}"
        )

        passed_entities = []
        failed_entities = []
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
                else:
                    failed_entities.append(parsed_entity)
            else:
                missing_required_fields = True
                entity_mapping_fault_counter += 1

        del calculated_entities_results

        self._notify_mapping_issues(
            entity_misconfigurations,
            missing_required_fields,
            entity_mapping_fault_counter,
        )

        return CalculationResult(
            EntitySelectorDiff(passed=passed_entities, failed=failed_entities),
            errors,
            misconfigured_entity_keys=entity_misconfigurations,
        )
