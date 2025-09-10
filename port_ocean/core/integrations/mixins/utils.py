from contextlib import contextmanager
from typing import Awaitable, Generator, Callable, cast

from loguru import logger
import asyncio
import multiprocessing
import uuid
import json
from port_ocean.core.handlers.entity_processor.jq_entity_processor import JQEntityProcessor
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
import os
from port_ocean.utils.async_http import _http_client
from port_ocean.clients.port.utils import _http_client as _port_http_client
from port_ocean.helpers.metric.metric import MetricType, MetricPhase
from port_ocean.context.ocean import ocean
import subprocess
import ijson
from typing import Any, AsyncGenerator

def _process_path_type_items(
    result: RAW_RESULT, items_to_parse: str | None = None
) -> RAW_RESULT:
    """
    Process items in the result array to check for "__type": "path" fields.
    If found, read the file contents and load them into a "content" field.
    Skip processing if we're on the items_to_parse branch.
    """
    if not isinstance(result, list):
        return result

    # Skip processing if we're on the items_to_parse branch
    if items_to_parse:
        return result

    processed_result = []
    for item in result:
        if isinstance(item, dict) and item.get("__type") == "path":
            try:
                # Read the file content and parse as JSON
                file_path = item.get("file", {}).get("content", {}).get("path")
                if file_path and os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        content = json.loads(f.read())
                    # Create a copy of the item with the content field
                    processed_item = item.copy()
                    processed_item["content"] = content
                    processed_result.append(processed_item)
                else:
                    # If file doesn't exist, keep the original item
                    processed_result.append(item)
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.warning(
                    f"Failed to read or parse file content for path "
                    f"{item.get('file', {}).get('content', {}).get('path')}: {e}"
                )
                # Keep the original item if there's an error
                processed_result.append(item)
        else:
            # Keep non-path type items as is
            processed_result.append(item)

    return processed_result

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
    fn: Callable[[str], Awaitable[RAW_RESULT]], kind: str
) -> RAW_RESULT:
    with resync_error_handling():
        results = await fn(kind)
        validated_results = validate_result(results)
        return _process_path_type_items(validated_results)


async def resync_generator_wrapper(
    fn: Callable[[str], ASYNC_GENERATOR_RESYNC_TYPE], kind: str, items_to_parse_name: str, items_to_parse: str | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    generator = fn(kind)
    errors = []
    try:
        while True:
            try:
                with resync_error_handling():
                    result = await anext(generator)
                    if not ocean.config.yield_items_to_parse:
                        validated_result = validate_result(result)
                        processed_result = _process_path_type_items(validated_result)
                        yield processed_result
                    else:
                        if items_to_parse:
                            for data in result:
                                bulks = get_items_to_parse_bulks(data, data.get("file", {}).get("content", {}).get("path", None), items_to_parse, items_to_parse_name, data.get("__base_jq", ".file.content"))
                                async for bulk in bulks:
                                    yield bulk
                        else:
                            validated_result = validate_result(result)
                            processed_result = _process_path_type_items(validated_result, items_to_parse)
                            yield processed_result
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

async def get_items_to_parse_bulks(raw_data: dict[Any, Any], data_path: str, items_to_parse: str, items_to_parse_name: str, base_jq: str) -> AsyncGenerator[list[dict[str, Any]], None]:
    items_to_parse = items_to_parse.replace(base_jq, ".") if data_path else items_to_parse
    if not data_path:
        raw_data_serialized = json.dumps(raw_data)
        data_path = f"/tmp/ocean/input_{uuid.uuid4()}.json"
        with open(data_path, "w") as f:
            f.write(raw_data_serialized)
    output_path = f"/tmp/ocean/parsed_{uuid.uuid4()}.json"
    delete_target = items_to_parse.split('|', 1)[0].strip() if not items_to_parse.startswith('map(') else '.'
    base_jq_object_string = await _build_base_jq_object_string(raw_data, base_jq, delete_target)
    jq_cmd = f"""/bin/jq '. as $all
      | ($all | {items_to_parse}) as $items
      | $items
      | map({{{items_to_parse_name}: ., {base_jq_object_string}}})
    ' {data_path} > {output_path}"""
    try:
        result = subprocess.run(jq_cmd, capture_output=True, text=True, shell=True, check=True)
        if result.stderr:
            logger.error(f"Failed to parse items for JQ expression {items_to_parse}, error: {result.stderr}")
            yield []
        else:
            with open(output_path, "r") as f:
                events_stream =get_events_as_a_stream(f, 'item', ocean.config.yield_items_to_parse_batch_size)
                for items_bulk in events_stream:
                    yield items_bulk
    except Exception as e:
        logger.error(f"Failed to parse items for JQ expression {items_to_parse}, error: {e}")
        yield []
    finally:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
            if os.path.exists(data_path):
                os.remove(data_path)
        except OSError as e:
            logger.warning(f"Failed to cleanup temporary files: {e}")

def unsupported_kind_response(
    kind: str, available_resync_kinds: list[str]
) -> tuple[RESYNC_RESULT, list[Exception]]:
    logger.error(f"Kind {kind} is not supported in this integration")
    return [], [KindNotImplementedException(kind, available_resync_kinds)]

async def _build_base_jq_object_string(raw_data: dict[Any, Any], base_jq: str, delete_target: str) -> str:
    base_jq_object_before_parsing = await cast(JQEntityProcessor, ocean.app.integration.entity_processor)._search(raw_data, f"{base_jq} = {json.dumps("__all")}")
    base_jq_object_before_parsing_serialized = json.dumps(base_jq_object_before_parsing)
    base_jq_object_before_parsing_serialized = base_jq_object_before_parsing_serialized[1:-1] if len(base_jq_object_before_parsing_serialized) >= 2 else base_jq_object_before_parsing_serialized
    base_jq_object_before_parsing_serialized = base_jq_object_before_parsing_serialized.replace("\"__all\"", f"(($all | del({delete_target})) // {{}})")
    return base_jq_object_before_parsing_serialized


def get_events_as_a_stream(
        stream: Any,
        target_items: str = "item",
        max_buffer_size_mb: int = 1
    ) -> Generator[list[dict[str, Any]], None, None]:
        events = ijson.sendable_list()
        coro = ijson.items_coro(events, target_items)

        # Convert MB to bytes for the buffer size
        buffer_size = max_buffer_size_mb * 1024 * 1024

        # Read chunks from the stream until exhausted
        while True:
            chunk = stream.read(buffer_size)
            if not chunk:  # End of stream
                break

            # Convert string to bytes if necessary (for text mode files)
            if isinstance(chunk, str):
                chunk = chunk.encode('utf-8')

            coro.send(chunk)
            yield events
            del events[:]
        try:
            coro.close()
        finally:
            if events:
                yield events
                events[:] = []

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

class _AiterReader:
    """
    Wraps an iterable of byte chunks (e.g., response.iter_bytes())
    and exposes a .read(n) method that ijson expects.
    """
    def __init__(self, iterable):
        self._iter = iter(iterable)
        self._buf = bytearray()
        self._eof = False

    def read(self, n=-1):
        # If n < 0, return everything until EOF
        if n is None or n < 0:
            chunks = [bytes(self._buf)]
            self._buf.clear()
            chunks.extend(self._iter)  # drain the iterator
            return b"".join(chunks)

        # Fill buffer until we have n bytes or hit EOF
        while len(self._buf) < n and not self._eof:
            try:
                self._buf.extend(next(self._iter))
            except StopIteration:
                self._eof = True
                break

        # Serve up to n bytes
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out
