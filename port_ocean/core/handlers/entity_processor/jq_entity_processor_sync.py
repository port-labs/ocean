import re
from typing import Any, cast

import jq  # type: ignore
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.entity_processor.models import MappedEntity
from port_ocean.exceptions.core import EntityProcessorException

_COMPILED_PATTERNS: dict[str, Any] = {}

# Common keys to probe when trying to identify a raw item in log messages.
_IDENTIFIER_KEYS = ("identifier", "id", "login", "name", "number", "key", "slug")


def _extract_item_identifier(data: dict[str, Any]) -> str | None:
    """Best-effort extraction of a human-readable identifier from a raw item.

    Used to enrich error logs with context about which source item caused a
    mapping failure, without dumping the entire raw object.
    """
    for key in _IDENTIFIER_KEYS:
        val = data.get(key)
        if val is not None:
            return str(val)
    return None


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
    def _search(
        data: dict[str, Any],
        pattern: str,
        # field and raw_item_identifier are passed through from _search_as_object
        # so every failure log names the exact mapping field and source item.
        field: str | None = None,
        raw_item_identifier: str | None = None,
    ) -> Any:
        try:
            compiled_pattern = JQEntityProcessorSync._compile(pattern)
            it = compiled_pattern.input_value(data)
            return next(iter(it), None)
        except Exception as exc:
            err_msg = str(exc) or repr(exc) or type(exc).__name__
            field_info = f" for field '{field}'" if field else ""
            item_info = (
                f" on item '{raw_item_identifier}'" if raw_item_identifier else ""
            )
            # Only the first line of the jq error — multiline messages are noisy.
            error_summary = err_msg.split("\n")[0]
            # Structured fields land in the log record's extra dict, keeping the
            # message string human-readable while still being machine-filterable in Port.
            logger.bind(
                field=field,
                pattern=pattern,
                error=err_msg,
                raw_item_identifier=raw_item_identifier,
            ).warning(
                f"Search failed{field_info}{item_info} - pattern: {pattern}: {error_summary}"
            )
            return None

    @staticmethod
    def _search_as_bool(data: dict[str, Any] | str, pattern: str) -> bool:
        # Wrapped in try/except so a compile or runtime error on the selector
        # raises EntityProcessorException with the pattern name, rather than
        # propagating a raw jq exception with no mapping context.
        try:
            compiled_pattern = JQEntityProcessorSync._compile(pattern)
            value = compiled_pattern.input_value(data).first()
        except Exception as exc:
            raise EntityProcessorException(
                f"Selector query failed for pattern {pattern!r}: {exc}"
            ) from exc
        if isinstance(value, bool):
            return value
        # Pattern name added so the error shows which selector produced a non-bool.
        raise EntityProcessorException(
            f"Expected boolean value for pattern {pattern!r}, got value:{value} of type: {type(value)} instead"
        )

    @staticmethod
    def _search_as_object(
        data: dict[str, Any],
        obj: dict[str, Any],
        misconfigurations: dict[str, str] | None = None,
        # _path is built up recursively to produce dot-notation field names
        # like "properties.url" instead of just "url" in misconfigurations and logs.
        _path: str = "",
        raw_item_identifier: str | None = None,
    ) -> dict[str, Any | None]:
        result: dict[str, Any | None | list[Any | None]] = {}
        for key, value in obj.items():
            current_path = f"{_path}.{key}" if _path else key
            try:
                if isinstance(value, list):
                    result[key] = []
                    for list_item in value:
                        search_result = JQEntityProcessorSync._search_as_object(
                            data,
                            list_item,
                            misconfigurations,
                            _path=current_path,
                            raw_item_identifier=raw_item_identifier,
                        )
                        cast(list[dict[str, Any | None]], result[key]).append(
                            search_result
                        )
                        if search_result is None and misconfigurations is not None:
                            # Use full dot-path as the key so callers can distinguish
                            # e.g. "properties.labels" from "relations.labels".
                            misconfigurations[current_path] = obj[key]

                elif isinstance(value, dict):
                    search_result = JQEntityProcessorSync._search_as_object(
                        data,
                        value,
                        misconfigurations,
                        _path=current_path,
                        raw_item_identifier=raw_item_identifier,
                    )
                    result[key] = search_result
                    if search_result is None and misconfigurations is not None:
                        misconfigurations[current_path] = obj[key]

                else:
                    search_result = JQEntityProcessorSync._search(
                        data,
                        value,
                        field=current_path,
                        raw_item_identifier=raw_item_identifier,
                    )
                    result[key] = search_result
                    if search_result is None and misconfigurations is not None:
                        # Store the JQ expression (value) rather than the resolved
                        # result so the misconfiguration log shows what was attempted.
                        misconfigurations[current_path] = value
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
            # Extract identifier once and thread it through all nested calls
            # so every log line for this item shares the same identifier context.
            raw_item_identifier = _extract_item_identifier(data)
            mapped_entity = JQEntityProcessorSync._search_as_object(
                data,
                raw_entity_mappings,
                misconfigurations,
                raw_item_identifier=raw_item_identifier,
            )
            return MappedEntity(
                entity=mapped_entity,
                did_entity_pass_selector=should_run,
                misconfigurations=misconfigurations,
            )

        return MappedEntity()
