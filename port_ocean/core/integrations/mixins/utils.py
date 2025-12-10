import asyncio
import multiprocessing
import re
from contextlib import contextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable, Generator, cast

from loguru import logger

from port_ocean.clients.port.utils import _http_client as _port_http_client
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers import JQEntityProcessor
from port_ocean.core.ocean_types import (
    ASYNC_GENERATOR_RESYNC_TYPE,
    RAW_RESULT,
    RESYNC_EVENT_LISTENER,
    RESYNC_RESULT,
)
from port_ocean.core.utils.utils import validate_result
from port_ocean.exceptions.core import (
    RawObjectValidationException,
    OceanAbortException,
    KindNotImplementedException,
)
from port_ocean.helpers.metric.metric import MetricType, MetricPhase
from port_ocean.utils.async_http import _http_client

def extract_jq_deletion_path_revised(jq_expression: str) -> str | None:
    """
    Revised function to extract a simple path suitable for del() by analyzing pipe segments.
    """
    expr = jq_expression.strip()

    # 1. Handle surrounding parentheses and extract the main chain
    if expr.startswith('('):
        match_paren = re.match(r'\((.*?)\)', expr, re.DOTALL)
        if match_paren:
            chain = match_paren.group(1).strip()
        else:
            return None
    else:
        chain = expr

    # 2. Split the chain by the main pipe operator (excluding pipes inside quotes or brackets,
    # but for simplicity here, we split naively and check segments)
    segments = chain.split('|')

    # 3. Analyze each segment for a simple path
    for segment in segments:
        segment = segment.strip()

        # Ignore variable assignment segments like '. as $root'
        if re.match(r'^\.\s+as\s+\$\w+', segment):
            continue

        # Ignore identity and variable access like '.' or '$items'
        if segment == '.' or segment.startswith('$'):
            continue

        # Look for the first genuine path accessor (e.g., .key, .[index], .key.nested, .key[0])
        # This regex looks for a starting dot and follows it with path components
        # (alphanumeric keys or bracketed accessors, where brackets can follow words directly)
        # Pattern: Start with .word or .[index], then optionally more:
        #   - .word (dot followed by word)
        #   - [index] (bracket directly after word, no dot)
        #   - .[index] (dot followed by bracket)
        path_match = re.match(r'(\.[\w]+|\.\[[^\]]+\])(\.[\w]+|\[[^\]]+\]|\.\[[^\]]+\])*', segment)

        if path_match:
            path = path_match.group(0).strip()

            # If the path is immediately followed by a simple fallback (// value),
            # we consider the path complete.
            if re.search(r'\s*//\s*(\[\]|null|\.|\{.*?\})', segment):
                return path

            # If the path is just a path segment followed by nothing or the end of a complex
            # expression (like .file.content.raw) we return it.
            return path

    # Default case: No suitable path found after checking all segments
    return None

@contextmanager
def resync_error_handling() -> Generator[None, None, None]:
    try:
        yield
    except RawObjectValidationException as error:
        err_msg = f"Failed to validate raw data for returned data from resync function, error: {error}"
        logger.exception(err_msg)
        raise OceanAbortException(err_msg) from error
    except StopAsyncIteration:
        raise
    except Exception as error:
        err_msg = f"Failed to execute resync function, error: {error}"
        logger.exception(err_msg)
        raise OceanAbortException(err_msg) from error


async def resync_function_wrapper(
    fn: Callable[[str], Awaitable[RAW_RESULT]], kind: str, items_to_parse: str | None = None
) -> RAW_RESULT:
    with resync_error_handling():
        results = await fn(kind)
        return validate_result(results)

async def handle_items_to_parse(result: RAW_RESULT, items_to_parse_name: str, items_to_parse: str | None = None) -> AsyncGenerator[list[dict[str, Any]], None]:
    delete_target = extract_jq_deletion_path_revised(items_to_parse) or '.'
    jq_expression = f". | del({delete_target})"
    batch_size = ocean.config.yield_items_to_parse_batch_size

    while len(result) > 0:
        item = result.pop(0)
        entity_processor = cast(JQEntityProcessor, ocean.app.integration.entity_processor)
        items_to_parse_data =  await entity_processor._search(item, items_to_parse)
        if event.resource_config.port.items_to_parse_top_level_transform:
            item = await entity_processor._search(item, jq_expression)
        if not isinstance(items_to_parse_data, list):
            logger.warning(
                f"Failed to parse items for JQ expression {items_to_parse}, Expected list but got {type(items_to_parse_data)}."
                f" Skipping..."
            )
            continue
        batch = []
        while len(items_to_parse_data) > 0:
            if (len(batch) >= batch_size):
                yield batch
                batch = []
            merged_item = {**item}
            merged_item[items_to_parse_name] = items_to_parse_data.pop(0)
            batch.append(merged_item)
        if len(batch) > 0:
            yield batch

async def resync_generator_wrapper(
    fn: Callable[[str], ASYNC_GENERATOR_RESYNC_TYPE], kind: str, items_to_parse_name: str, items_to_parse: str | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    generator = fn(kind)
    errors = []
    try:
        while True:
            try:
                with resync_error_handling():
                    result = validate_result(await anext(generator))

                    if items_to_parse:
                        items_to_parse_generator = handle_items_to_parse(result, items_to_parse_name, items_to_parse)
                        del result
                        async for batch in items_to_parse_generator:
                            yield batch
                    else:
                        yield result


            except OceanAbortException as error:
                errors.append(error)
                ocean.metrics.inc_metric(
                    name=MetricType.OBJECT_COUNT_NAME,
                    labels=[ocean.metrics.current_resource_kind(), MetricPhase.EXTRACT , MetricPhase.ExtractResult.FAILED],
                    value=1
                )
    except StopAsyncIteration:
        if errors:
            raise ExceptionGroup(
                "At least one of the resync generator iterations failed", errors
            )


def is_resource_supported(
    kind: str, resync_event_mapping: dict[str | None, list[RESYNC_EVENT_LISTENER]]
) -> bool:
    return bool(resync_event_mapping[kind] or resync_event_mapping[None])

def unsupported_kind_response(
    kind: str, available_resync_kinds: list[str]
) -> tuple[RESYNC_RESULT, list[Exception]]:
    logger.error(f"Kind {kind} is not supported in this integration")
    return [], [KindNotImplementedException(kind, available_resync_kinds)]

class ProcessWrapper(multiprocessing.Process):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def join_async(self) -> None:
        while self.exitcode is None:
            await asyncio.sleep(2)
        if self.exitcode != 0:
            logger.error(f"Process {self.pid} failed with exit code {self.exitcode}")
        else:
            logger.info(f"Process {self.pid} finished with exit code {self.exitcode}")
        return super().join()

def clear_http_client_context() -> None:
    try:
        while _http_client.top is not None:
            _http_client.pop()
    except (RuntimeError, AttributeError):
        pass

    try:
        while _port_http_client.top is not None:
            _port_http_client.pop()
    except (RuntimeError, AttributeError):
        pass
