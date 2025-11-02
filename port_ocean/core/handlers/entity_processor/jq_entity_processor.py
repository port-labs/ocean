import asyncio
from asyncio import Task
from dataclasses import dataclass, field
from functools import lru_cache
import json
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
from port_ocean.core.handlers.entity_processor.jq_input_evaluator import (
    InputClassifyingResult,
    classify_input,
    can_expression_run_with_no_input,
)


class ExampleStates:
    __succeed: list[dict[str, Any]]
    __errors: list[dict[str, Any]]
    __max_size: int

    def __init__(self, max_size: int = 0) -> None:
        """
        Store two sequences:
          - succeed: items that succeeded
          - errors:  items that failed
        """
        self.__succeed = []
        self.__errors = []
        self.__max_size = max_size

    def add_example(self, succeed: bool, item: dict[str, Any]) -> None:
        if succeed:
            self.__succeed.append(item)
        else:
            self.__errors.append(item)

    def __len__(self) -> int:
        """
        Total number of items (successes + errors).
        """
        return len(self.__succeed) + len(self.__errors)

    def get_examples(self, number: int = 0) -> list[dict[str, Any]]:
        """
        Return a list of up to number items, taking successes first,
        """
        if number <= 0:
            number = self.__max_size
        # how many from succeed?
        s_count = min(number, len(self.__succeed))
        result = list(self.__succeed[:s_count])
        # how many more from errors?
        e_count = number - s_count
        if e_count > 0:
            result.extend(self.__errors[:e_count])
        return result


@dataclass
class MappedEntity:
    """Represents the entity after applying the mapping

    This class holds the mapping entity along with the selector boolean value and optionally the raw data.
    """

    entity: dict[str, Any] = field(default_factory=dict)
    did_entity_pass_selector: bool = False
    raw_data: Optional[dict[str, Any] | tuple[dict[str, Any], str]] = None
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
            logger.error(
                f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
            )
            return None

    @lru_cache
    async def _search_stringified(self, data: str, pattern: str) -> Any:
        try:
            loop = asyncio.get_event_loop()
            compiled_pattern = self._compile(pattern)
            func = compiled_pattern.input_text(data)
            return await loop.run_in_executor(
                None, self._stop_iterator_handler(func.first)
            )
        except Exception as exc:
            logger.debug(
                f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
            )
            return None

    async def _search_as_bool(self, data: dict[str, Any] | str, pattern: str) -> bool:
        loop = asyncio.get_event_loop()

        compiled_pattern = self._compile(pattern)
        if isinstance(data, str):
            func = compiled_pattern.input_text(data)
        else:
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
        data: dict[str, Any] | str,
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
                if isinstance(data, str):
                    search_tasks[key] = asyncio.create_task(
                        self._search_stringified(data, value)
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
        data: dict[str, Any] | tuple[dict[str, Any], str],
        raw_entity_mappings: dict[str, Any],
        items_to_parse_key: str | None,
        selector_query: str,
        parse_all: bool = False,
    ) -> MappedEntity:
        should_run = await self._should_map_entity(
            data, selector_query, items_to_parse_key
        )
        if parse_all or should_run:
            misconfigurations, mapped_entity = await self._map_entity(
                data, raw_entity_mappings, items_to_parse_key
            )
            return MappedEntity(
                mapped_entity,
                did_entity_pass_selector=should_run,
                raw_data=data,
                misconfigurations=misconfigurations,
            )

        return MappedEntity(
            {},
            did_entity_pass_selector=False,
            raw_data=data,
            misconfigurations={},
        )

    async def _map_entity(
        self,
        data: dict[str, Any] | tuple[dict[str, Any], str],
        raw_entity_mappings: dict[str, Any],
        items_to_parse_key: str | None,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        if not items_to_parse_key:
            # No items to parse, map the entity and return the misconfigurations and the mapped entity
            misconfigurations: dict[str, str] = {}
            data_to_search = data if isinstance(data, dict) else data[0]
            mapped_entity = await self._search_as_object(
                data_to_search, raw_entity_mappings, misconfigurations
            )
            return misconfigurations, mapped_entity

        modified_data: tuple[dict[str, Any], str | dict[str, Any]] = (
            data
            if isinstance(data, tuple)
            else (
                {items_to_parse_key: data[items_to_parse_key]},
                data,
            )
        )

        misconfigurations_item: dict[str, str] = {}
        misconfigurations_all: dict[str, str] = {}
        # Map the entity with jq expressions that classified as single item expressions with the single item as input
        mapped_entity_item = await self._search_as_object(
            modified_data[0], raw_entity_mappings["item"], misconfigurations_item
        )
        # To Prevent misclassification data loss, we merge the expressions that classified as single item expressions and resulted as misconfigured
        # into the expressions that classified as all expressions
        if misconfigurations_item:
            # The misconfigurations dict not contains the mapping expressions themselves, so we need to filter the original mapping by the misconfigured keys
            filtered_item_mappings = self._filter_mappings_by_keys(
                raw_entity_mappings["item"], list(misconfigurations_item.keys())
            )
            raw_entity_mappings["all"] = self._deep_merge(
                raw_entity_mappings["all"], filtered_item_mappings
            )
        # Map the entity with jq expressions that classified as all expressions with the whole data as input
        mapped_entity_all = await self._search_as_object(
            modified_data[1], raw_entity_mappings["all"], misconfigurations_all
        )
        # Map the entity with jq expressions that classified as no input required expressions with empty object as input
        mapped_entity_empty = await self._search_as_object(
            {}, raw_entity_mappings["empty"], misconfigurations_all
        )
        # Merge the mapped entities
        mapped_entity = self._deep_merge(mapped_entity_item, mapped_entity_all)
        mapped_entity = self._deep_merge(mapped_entity, mapped_entity_empty)
        return misconfigurations_all, mapped_entity

    async def _should_map_entity(
        self,
        data: dict[str, Any] | tuple[dict[str, Any], str],
        selector_query: str,
        items_to_parse_key: str | None,
    ) -> bool:
        if can_expression_run_with_no_input(selector_query):
            return await self._search_as_bool({}, selector_query)
        if isinstance(data, tuple):
            return await self._search_as_bool(
                data[0], selector_query
            ) or await self._search_as_bool(data[1], selector_query)
        if items_to_parse_key:
            return await self._search_as_bool(
                data[items_to_parse_key], selector_query
            ) or await self._search_as_bool(data, selector_query)
        return await self._search_as_bool(data, selector_query)

    async def _calculate_entity(
        self,
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        items_to_parse: str | None,
        items_to_parse_name: str,
        selector_query: str,
        parse_all: bool = False,
    ) -> tuple[list[MappedEntity], list[Exception]]:
        raw_data: list[dict[str, Any]] | list[tuple[dict[str, Any], str]] = [
            data.copy()
        ]
        items_to_parse_key = None
        if items_to_parse:
            items_to_parse_key = items_to_parse_name
            if not ocean.config.yield_items_to_parse:
                if isinstance(data, dict) and data.get("__type") == "path":
                    file_path = data.get("file", {}).get("content", {}).get("path")
                    with open(file_path, "r") as f:
                        data["file"]["content"] = json.loads(f.read())
                items = await self._search(data, items_to_parse)
                if not isinstance(items, list):
                    logger.warning(
                        f"Failed to parse items for JQ expression {items_to_parse}, Expected list but got {type(items)}."
                        f" Skipping..."
                    )
                    return [], []
                raw_all_payload_stringified = json.dumps(data)
                raw_data = [
                    ({items_to_parse_name: item}, raw_all_payload_stringified)
                    for item in items
                ]
            single_item_mappings, all_items_mappings, empty_items_mappings = (
                self._build_raw_entity_mappings(
                    raw_entity_mappings, items_to_parse_name
                )
            )
            raw_entity_mappings = {
                "item": single_item_mappings,
                "all": all_items_mappings,
                "empty": empty_items_mappings,
            }

        entities, errors = await gather_and_split_errors_from_results(
            [
                self._get_mapped_entity(
                    raw,
                    raw_entity_mappings,
                    items_to_parse_key,
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

    def _build_raw_entity_mappings(
        self, raw_entity_mappings: dict[str, Any], items_to_parse_name: str
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """
        Build the raw entity mappings for the items to parse.
        The mappings are grouped by the input classifying result.
        There are 3 input classifying results:
            - NONE: The expression can be executed with no input
            - SINGLE: The expression can be executed on a single item
            - ALL: The expression can be executed on all the data
        """
        mappings: dict[InputClassifyingResult, dict[str, Any]] = {
            InputClassifyingResult.NONE: {},
            InputClassifyingResult.SINGLE: {},
            InputClassifyingResult.ALL: {},
        }
        for key, value in raw_entity_mappings.items():
            if isinstance(value, str):
                # Direct string values (identifier, title, icon, blueprint, team)
                self.group_string_mapping_value(
                    items_to_parse_name,
                    mappings,
                    key,
                    value,
                )
            elif isinstance(value, dict):
                # Complex objects (IngestSearchQuery for identifier/team, properties, relations)
                self.group_complex_mapping_value(
                    items_to_parse_name,
                    mappings,
                    key,
                    value,
                )
        return (
            mappings[InputClassifyingResult.SINGLE],
            mappings[InputClassifyingResult.ALL],
            mappings[InputClassifyingResult.NONE],
        )

    def group_complex_mapping_value(
        self,
        pattern: str,
        mappings: dict[InputClassifyingResult, dict[str, Any]],
        key: str,
        value: dict[str, Any],
    ) -> None:

        if key in ["properties", "relations"]:
            mapping_dicts: dict[InputClassifyingResult, dict[str, Any]] = {
                InputClassifyingResult.SINGLE: {},
                InputClassifyingResult.ALL: {},
                InputClassifyingResult.NONE: {},
            }
            # For properties and relations, filter the dictionary values
            for dict_key, dict_value in value.items():
                if isinstance(dict_value, str):
                    self.group_string_mapping_value(
                        pattern,
                        mapping_dicts,
                        dict_key,
                        dict_value,
                    )
                elif isinstance(dict_value, dict):
                    # Handle IngestSearchQuery objects
                    self.group_search_query_mapping_value(
                        pattern,
                        mapping_dicts[InputClassifyingResult.SINGLE],
                        mapping_dicts[InputClassifyingResult.ALL],
                        dict_key,
                        dict_value,
                    )
            for input_classifying_result, mapping_dict in mapping_dicts.items():
                if mapping_dict:
                    mappings[input_classifying_result][key] = mapping_dict
        else:
            # For identifier/team IngestSearchQuery objects
            self.group_search_query_mapping_value(
                pattern,
                mappings[InputClassifyingResult.SINGLE],
                mappings[InputClassifyingResult.ALL],
                key,
                value,
            )

    def group_search_query_mapping_value(
        self,
        pattern: str,
        single_item_dict: dict[str, Any],
        all_item_dict: dict[str, Any],
        dict_key: str,
        dict_value: dict[str, Any],
    ) -> None:
        if self._classify_search_query(dict_value, pattern):
            single_item_dict[dict_key] = dict_value
        else:
            all_item_dict[dict_key] = dict_value

    def group_string_mapping_value(
        self,
        pattern: str,
        mappings: dict[InputClassifyingResult, dict[str, Any]],
        key: str,
        value: str,
    ) -> None:
        input_evaluation_result = classify_input(value, pattern)
        mappings[input_evaluation_result][key] = value

    def _classify_search_query(self, query_dict: dict[str, Any], pattern: str) -> bool:
        """
        Classify the input required to run jq expressions of an IngestSearchQuery
        If at least one rule contains a value that includes the pattern, return True
        Otherwise, return False
        Example:
        The pattern is item
        relations:
            someRelation:
              combinator: "and"
              rules:
                - operator: "="
                  property: "someProperty"
                  value: .field
                - combinator: "or"
                  rules:
                    - operator: "="
                      property: "anotherProperty"
                      value: .item.something
                    - operator: "="
                      property: "yetAnotherProperty"
                      value: .yetAnotherValue
        One value is .item.something, which is a single item based expression, so it will be classified as SINGLE
        """
        if "rules" not in query_dict:
            return False

        rules = query_dict["rules"]
        if not isinstance(rules, list):
            return False

        # Check if any rule contains a value that includes the pattern
        for rule in rules:
            if isinstance(rule, dict) and self._is_rule_or_query_contains_pattern(
                rule, pattern
            ):
                return True
        return False

    def _is_rule_or_query_contains_pattern(
        self, rule: dict[str, Any], pattern: str
    ) -> bool:
        """
        Check if a rule or query contains a value that includes the pattern
        If the value is a single item based expression, return True
        Otherwise, return False
        Example:
        The pattern is item
        The rule is:
                - combinator: "or"
                  rules:
                    - operator: "="
                      property: "anotherProperty"
                      value: .item.something
                    - operator: "="
                      property: "yetAnotherProperty"
                      value: .yetAnotherValue
        This rule is not a single rule (not contains a value property) but a search query rule (contains a rules property)
        so we need to recursively check the rules property to check if at least one rule contains a value that includes the pattern
        In this case, one value is .item.something, which is a single item based expression, so it will be classified as SINGLE ==> true
        """
        if "value" in rule and isinstance(rule["value"], str):
            # Use evaluate_input to check if the pattern is relevant for this value
            input_evaluation_result = classify_input(rule["value"], pattern)
            if input_evaluation_result == InputClassifyingResult.SINGLE:
                return True
        # Recursively check nested IngestSearchQuery objects
        elif "rules" in rule:
            if self._classify_search_query(rule, pattern):
                return True
        return False

    def _filter_mappings_by_keys(
        self, mappings: dict[str, Any], target_keys: list[str]
    ) -> dict[str, Any]:
        """
        Filter mappings to preserve structure with only the specified keys present.
        Recursively handles nested dictionaries and lists, searching for keys at any level.

        Args:
            mappings: The dictionary containing mapping configurations to filter
            target_keys: List of keys to preserve in the filtered result

        Returns:
            A filtered dictionary containing only the specified keys and their nested structures

        Examples:
            # Basic filtering with direct keys
            mappings = {
                "name": "John",
                "age": 30,
                "city": "New York",
                "country": "USA"
            }
            target_keys = ["name", "age"]
            result = self._filter_mappings_by_keys(mappings, target_keys)
            # Returns: {"name": "John", "age": 30}

            # Nested dictionary filtering
            mappings = {
                "user": {
                    "profile": {"name": "John", "email": "john@example.com"},
                    "settings": {"theme": "dark", "notifications": True}
                },
                "metadata": {"created_at": "2023-01-01", "version": "1.0"}
            }
            target_keys = ["name", "email", "created_at"]
            result = self._filter_mappings_by_keys(mappings, target_keys)
            # Returns: {
            #     "user": {
            #         "profile": {"name": "John", "email": "john@example.com"}
            #     },
            #     "metadata": {"created_at": "2023-01-01"}
            # }

            # Empty target keys returns empty dict
            result = self._filter_mappings_by_keys(mappings, [])
            # Returns: {}
        """
        if not target_keys:
            return {}

        filtered_mappings: dict[str, Any] = {}

        for key, value in mappings.items():
            filtered_value = self._process_mapping_value(key, value, target_keys)

            # Include if it's a direct match or contains nested target keys
            if key in target_keys or filtered_value:
                filtered_mappings[key] = filtered_value

        return filtered_mappings

    def _process_mapping_value(
        self, key: str, value: Any, target_keys: list[str]
    ) -> Any:
        """
        Process a single mapping value, handling different types recursively.

        This helper method is used by _filter_mappings_by_keys to process individual
        key-value pairs. It handles both simple values and nested dictionaries,
        applying the filtering logic recursively to maintain the hierarchical structure.

        Args:
            key: The key of the current mapping item being processed
            value: The value associated with the key (can be any type)
            target_keys: List of keys to preserve in the filtered result

        Returns:
            The processed value if it should be included, None otherwise.
            For dictionaries, returns the filtered dictionary or None if empty.
            For simple values, returns the value if the key is in target_keys, None otherwise.

        Examples:
            # Simple value processing - key in target_keys
            result = self._process_mapping_value("name", "John", ["name", "age"])
            # Returns: "John"

            # Simple value processing - key not in target_keys
            result = self._process_mapping_value("city", "New York", ["name", "age"])
            # Returns: None

            # Dictionary processing with nested target keys
            nested_dict = {
                "profile": {"name": "John", "email": "john@example.com"},
                "settings": {"theme": "dark"}
            }
            result = self._process_mapping_value("user", nested_dict, ["name", "email"])
            # Returns: {"profile": {"name": "John", "email": "john@example.com"}}

            # Dictionary processing with no matching target keys
            result = self._process_mapping_value("user", nested_dict, ["version"])
            # Returns: None
        """
        if isinstance(value, dict):
            # Recursively filter nested dictionary
            filtered_dict = self._filter_mappings_by_keys(value, target_keys)
            return filtered_dict if filtered_dict else None
        else:
            # Return simple values as-is
            return value if key in target_keys else None

    def _deep_merge(
        self, dict1: dict[str, Any], dict2: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Deep merge two dictionaries, preserving nested structures.
        Values from dict2 override values from dict1 for the same keys.
        """
        result = dict1.copy()

        for key, value in dict2.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            elif (
                key in result
                and isinstance(result[key], list)
                and isinstance(value, list)
            ):
                # Merge lists by extending
                result[key].extend(value)
            else:
                # Override with value from dict2
                result[key] = value

        return result

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
                mapping.port.items_to_parse_name,
                mapping.selector.query,
                parse_all,
            )
        )
        logger.debug(
            f"Finished parsing raw results into entities with {len(errors)} errors. errors: {errors}"
        )

        passed_entities = []
        failed_entities = []
        examples_to_send = ExampleStates(send_raw_data_examples_amount)
        entity_misconfigurations: dict[str, str] = {}
        missing_required_fields: bool = False
        entity_mapping_fault_counter: int = 0
        for result in calculated_entities_results:
            if len(result.misconfigurations) > 0:
                entity_misconfigurations |= result.misconfigurations

            if (
                len(examples_to_send) < send_raw_data_examples_amount
                and result.raw_data is not None
            ):
                examples_to_send.add_example(
                    result.did_entity_pass_selector,
                    self._get_raw_data_for_example(
                        result.raw_data, mapping.port.items_to_parse_name
                    ),
                )

            if result.entity.get("identifier") and result.entity.get("blueprint"):
                parsed_entity = Entity.parse_obj(result.entity)
                if result.did_entity_pass_selector:
                    passed_entities.append(parsed_entity)
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

        await self._send_examples(examples_to_send.get_examples(), mapping.kind)

        return CalculationResult(
            EntitySelectorDiff(passed=passed_entities, failed=failed_entities),
            errors,
            misconfigured_entity_keys=entity_misconfigurations,
        )

    def _get_raw_data_for_example(
        self,
        data: dict[str, Any] | tuple[dict[str, Any], str],
        items_to_parse_name: str,
    ) -> dict[str, Any]:
        if isinstance(data, tuple):
            raw_data = json.loads(data[1])
            return {
                **(
                    data[0]
                    if items_to_parse_name in data[0]
                    else {items_to_parse_name: data[0]}
                ),
                **raw_data,
            }
        return data
