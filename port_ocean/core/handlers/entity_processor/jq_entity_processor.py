import asyncio
from asyncio.tasks import Task
from functools import lru_cache
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import re
from typing import Any, cast

import jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.entity_processor.base import BaseEntityProcessor
from port_ocean.core.handlers.entity_processor.jq_entity_processor_sync import (
    JQEntityProcessorSync,
)
from port_ocean.core.handlers.entity_processor.models import MappedEntity
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.models import Entity
from port_ocean.core.ocean_types import (
    RAW_ITEM,
    CalculationResult,
    EntitySelectorDiff,
)
from port_ocean.core.utils.utils import (
    gather_and_split_errors_from_results,
)
from port_ocean.exceptions.core import EntityProcessorException


# Set globals for multiprocessing of batch data. When a process forks, it inherits these globals by reference.
# We will take advantage of COW to avoid pickling the data.
_MULTIPROCESS_JQ_BATCH_DATA: list[dict[str, Any]] | None = None
_MULTIPROCESS_JQ_BATCH_MAPPINGS: dict[str, Any] | None = None
_MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY: str | None = None
_MULTIPROCESS_JQ_BATCH_PARSE_ALL: bool | None = None


def _calculate_entity(
    index: int,
) -> tuple[list[MappedEntity], list[Exception]]:
    # Access data directly from globals to avoid pickling.
    global _MULTIPROCESS_JQ_BATCH_DATA, _MULTIPROCESS_JQ_BATCH_MAPPINGS, _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY, _MULTIPROCESS_JQ_BATCH_PARSE_ALL
    if None in [
        _MULTIPROCESS_JQ_BATCH_DATA,
        _MULTIPROCESS_JQ_BATCH_MAPPINGS,
        _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY,
        _MULTIPROCESS_JQ_BATCH_PARSE_ALL,
    ]:
        return [], [Exception("Missing data for index: {index}")]
    batch_data = cast(list[dict[str, Any]], _MULTIPROCESS_JQ_BATCH_DATA)
    data = batch_data[index]
    raw_entity_mappings = cast(dict[str, Any], _MULTIPROCESS_JQ_BATCH_MAPPINGS)
    selector_query = cast(str, _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY)
    parse_all = cast(bool, _MULTIPROCESS_JQ_BATCH_PARSE_ALL)

    try:
        entity = JQEntityProcessorSync._get_mapped_entity(
            data,
            raw_entity_mappings,
            selector_query,
            parse_all,
        )
        return [entity], []
    except Exception as e:
        if isinstance(e, BaseException) and not isinstance(e, Exception):
            raise e
        elif isinstance(e, Exception):
            return [], [e]


class JQEntityProcessor(BaseEntityProcessor):
    """Processes and parses entities using JQ expressions.

    This class extends the BaseEntityProcessor and provides methods for processing and
    parsing entities based on PyJQ queries. It supports compiling and executing PyJQ patterns,
    searching for data in dictionaries, and transforming data based on object mappings.
    """

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
                entity=mapped_entity,
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
        pattern = self._format_filter(pattern)
        if not ocean.config.allow_environment_variables_jq_access:
            pattern = "def env: {}; {} as $ENV | " + pattern
        compiled_pattern = jq.compile(pattern)
        return compiled_pattern

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

    async def separate_compileable_and_uncompileable_patterns_and_warmup_cache(
        self, raw_entity_mappings: dict[str, Any], selector_queries: list[str] = []
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        uncompileable_patterns: dict[str, Any] = {}
        compileable_patterns: dict[str, Any] = {}
        for key, value in raw_entity_mappings.items():

            if isinstance(value, dict):
                compileable_patterns[key], uncompileable_patterns[key] = (
                    await self.separate_compileable_and_uncompileable_patterns_and_warmup_cache(
                        value
                    )
                )
            else:
                try:
                    self._compile(value)
                    compileable_patterns[key] = value
                except Exception:
                    uncompileable_patterns[key] = value

        for selector_query in selector_queries:
            try:
                self._compile(selector_query)
            except Exception:
                pass
        return compileable_patterns, uncompileable_patterns

    async def parse_items_sync(
        self,
        compileable_patterns: dict[str, Any],
        raw_results: list[RAW_ITEM],
        selector_query: str,
        parse_all: bool = False,
    ) -> tuple[list[tuple[list[MappedEntity], list[Exception]]], list[Exception]]:

        global _MULTIPROCESS_JQ_BATCH_DATA, _MULTIPROCESS_JQ_BATCH_MAPPINGS, _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY, _MULTIPROCESS_JQ_BATCH_PARSE_ALL

        _MULTIPROCESS_JQ_BATCH_DATA = raw_results
        _MULTIPROCESS_JQ_BATCH_MAPPINGS = compileable_patterns
        _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = selector_query
        _MULTIPROCESS_JQ_BATCH_PARSE_ALL = parse_all
        # Fork a new process to calculate the entities.
        # Use indexes to acess data to have the lowest pickling overhead.
        loop = asyncio.get_running_loop()
        with ProcessPoolExecutor(
            max_workers=ocean.config.process_in_queue_max_workers,
            mp_context=multiprocessing.get_context("fork"),
        ) as pool:
            results = await gather_and_split_errors_from_results(
                [
                    asyncio.wait_for(
                        loop.run_in_executor(pool, _calculate_entity, index),
                        timeout=ocean.config.process_in_queue_timeout,
                    )
                    for index in range(len(raw_results))
                ]
            )
        # Clear globals to avoid memory leaks.
        _MULTIPROCESS_JQ_BATCH_DATA = None
        _MULTIPROCESS_JQ_BATCH_MAPPINGS = None
        _MULTIPROCESS_JQ_BATCH_SELECTOR_QUERY = None
        _MULTIPROCESS_JQ_BATCH_PARSE_ALL = None
        return results

    async def parse_items_async(
        self,
        uncompiled_patterns: dict[str, Any],
        raw_results: list[RAW_ITEM],
        selector_query: str,
        parse_all: bool = False,
    ) -> tuple[list[tuple[list[MappedEntity], list[Exception]]], list[Exception]]:

        if len(uncompiled_patterns.keys()) == 0:
            return [], []
        results = await gather_and_split_errors_from_results(
            [
                self._calculate_entity(
                    raw, uncompiled_patterns, selector_query, parse_all
                )
                for raw in raw_results
            ]
        )
        return results

    def _deep_merge(
        self, dict1: dict[str, Any], dict2: dict[str, Any]
    ) -> dict[str, Any]:
        for key, value in dict2.items():
            # If both values are dictionaries, merge them recursively
            if key in dict1:
                if isinstance(dict1[key], dict) and isinstance(value, dict):
                    dict1[key] = self._deep_merge(dict1[key], value)
            else:
                # only add new values
                dict1[key] = value
        return dict1

    def merge_results(
        self,
        jq_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ],
        async_results: tuple[
            list[tuple[list[MappedEntity], list[Exception]]], list[Exception]
        ],
        raw_results: list[RAW_ITEM],
    ) -> tuple[list[MappedEntity], list[Exception]]:
        errors: list[Exception] = []
        calculated_entities_results: list[MappedEntity] = []

        actual_jq_results, jq_errors = jq_results
        actual_async_results, async_errors = async_results

        original_result_size = len(raw_results)
        jq_results_size = len(actual_jq_results)
        async_results_size = len(actual_async_results)
        # checkout gather and split, there are some execptions we want raise
        if len(jq_errors) > 0 or len(async_errors) > 0:
            raise ExceptionGroup("Error processing tasks", jq_errors + async_errors)
        # if didnt run since no uncompiled patterns found
        if async_results_size == 0:
            for result in actual_jq_results:
                entities, jq_errors = result
                calculated_entities_results.extend(entities)
                errors.extend(jq_errors)
            return calculated_entities_results, errors

        errors.extend(async_errors)

        # Since we use gather on the same data, we can assume of we
        for index in range(original_result_size):
            if jq_results_size != async_results_size:
                logger.warning(
                    f"jq results size {jq_results_size} does not match async results size {async_results_size}"
                )

            if index > jq_results_size or index > async_results_size:
                logger.error(
                    f"Index {index} is out of bounds for jq_results or async_results"
                )
                break

            jq_result, jq_error = actual_jq_results[index]
            async_result, async_error = actual_async_results[index]

            if jq_error:
                errors.extend(jq_error)
            if async_error:
                errors.extend(async_error)

            if len(jq_result) > 0 and len(async_result) > 0:
                jq_mapped_entity = jq_result[0]
                async_mapped_entity = async_result[0]

                did_entity_pass_selector = (
                    jq_mapped_entity.did_entity_pass_selector
                    and async_mapped_entity.did_entity_pass_selector
                )

                new_entity = self._deep_merge(
                    jq_mapped_entity.entity, async_mapped_entity.entity
                )
                misconfigurations = self._deep_merge(
                    jq_mapped_entity.misconfigurations,
                    async_mapped_entity.misconfigurations,
                )
                calculated_entities_results.append(
                    MappedEntity(
                        entity=new_entity,
                        did_entity_pass_selector=did_entity_pass_selector,
                        misconfigurations=misconfigurations,
                    )
                )
                continue
            if len(jq_result) > 0 and len(async_result) == 0:
                calculated_entities_results.append(jq_result[0])
                continue
            if len(jq_result) == 0 and len(async_result) > 0:
                calculated_entities_results.append(async_result[0])
                continue

        return calculated_entities_results, errors

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
        compileable_patterns, uncompileable_patterns = (
            await self.separate_compileable_and_uncompileable_patterns_and_warmup_cache(
                raw_entity_mappings, [mapping.selector.query]
            )
        )
        sync_results = await self.parse_items_sync(
            compileable_patterns, raw_results, mapping.selector.query, parse_all
        )
        async_results = await self.parse_items_async(
            uncompileable_patterns, raw_results, mapping.selector.query, parse_all
        )
        calculated_entities_results, errors = self.merge_results(
            sync_results, async_results, raw_results
        )
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
