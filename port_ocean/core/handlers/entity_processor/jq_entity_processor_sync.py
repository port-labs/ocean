import re
from typing import Any, cast

import jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.entity_processor.models import MappedEntity
from port_ocean.exceptions.core import EntityProcessorException

_COMPILED_PATTERNS: dict[str, Any] = {}


class JQEntityProcessorSync:
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

    @staticmethod
    def _compile(pattern: str) -> Any:
        pattern = JQEntityProcessorSync._format_filter(pattern)
        if not ocean.config.allow_environment_variables_jq_access:
            pattern = "def env: {}; {} as $ENV | " + pattern
        if pattern in _COMPILED_PATTERNS:

            return _COMPILED_PATTERNS[pattern]
        compiled_pattern = jq.compile(pattern)
        _COMPILED_PATTERNS[pattern] = compiled_pattern
        return compiled_pattern

    @staticmethod
    def _search(data: dict[str, Any], pattern: str) -> Any:
        try:
            compiled_pattern = JQEntityProcessorSync._compile(pattern)
            return compiled_pattern.input_value(data).first()
        except Exception as exc:
            logger.error(
                f"Search failed for pattern '{pattern}' in data: {data}, Error: {exc}"
            )
            return None

    @staticmethod
    def _search_as_bool(data: dict[str, Any] | str, pattern: str) -> bool:
        compiled_pattern = JQEntityProcessorSync._compile(pattern)
        value = compiled_pattern.input_value(data).first()
        if isinstance(value, bool):
            return value
        raise EntityProcessorException(
            f"Expected boolean value, got value:{value} of type: {type(value)} instead"
        )

    @staticmethod
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
                        search_result = JQEntityProcessorSync._search_as_object(
                            data, list_item, misconfigurations
                        )
                        cast(list[dict[str, Any | None]], result[key]).append(
                            search_result
                        )
                        if search_result is None and misconfigurations is not None:
                            misconfigurations[key] = obj[key]

                elif isinstance(value, dict):
                    search_result = JQEntityProcessorSync._search_as_object(
                        data, value, misconfigurations
                    )
                    result[key] = search_result
                    if search_result is None and misconfigurations is not None:
                        misconfigurations[key] = obj[key]

                else:
                    search_result = JQEntityProcessorSync._search(data, value)
                    result[key] = search_result
                    if search_result is None and misconfigurations is not None:
                        misconfigurations[key] = obj[key]
            except Exception:
                result[key] = None

        return result

    @staticmethod
    def _get_mapped_entity(
        data: dict[str, Any],
        raw_entity_mappings: dict[str, Any],
        selector_query: str,
        parse_all: bool = False,
    ) -> MappedEntity:
        should_run = JQEntityProcessorSync._search_as_bool(data, selector_query)
        if parse_all or should_run:
            misconfigurations: dict[str, str] = {}
            mapped_entity = JQEntityProcessorSync._search_as_object(
                data, raw_entity_mappings, misconfigurations
            )
            return MappedEntity(
                entity=mapped_entity,
                did_entity_pass_selector=should_run,
                misconfigurations=misconfigurations,
            )

        return MappedEntity()
