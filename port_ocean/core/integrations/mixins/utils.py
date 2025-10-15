from contextlib import contextmanager
from typing import Awaitable, Generator, Callable, cast

from loguru import logger

import asyncio
import multiprocessing

from port_ocean.core.handlers.entity_processor.jq_entity_processor import JQEntityProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
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

from port_ocean.utils.async_http import _http_client
from port_ocean.clients.port.utils import _http_client as _port_http_client
from port_ocean.helpers.metric.metric import MetricType, MetricPhase
from port_ocean.context.ocean import ocean

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
        return validate_result(results)


async def resync_generator_wrapper(
    fn: Callable[[str], ASYNC_GENERATOR_RESYNC_TYPE], kind: str, items_to_parse: str | None = None
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    generator = fn(kind)
    errors = []
    try:
        while True:
            try:
                with resync_error_handling():
                    result = await anext(generator)
                    if not ocean.config.yield_items_to_parse:
                        yield validate_result(result)
                    else:
                        batch_size = ocean.config.yield_items_to_parse_batch_size
                        if items_to_parse:
                            for data in result:
                                items = await cast(JQEntityProcessor, ocean.app.integration.entity_processor)._search(data, items_to_parse)
                                if not isinstance(items, list):
                                    logger.warning(
                                        f"Failed to parse items for JQ expression {items_to_parse}, Expected list but got {type(items)}."
                                        f" Skipping..."
                                    )
                                    yield []
                                raw_data = [{"item": item, **data} for item in items]
                                while True:
                                    raw_data_batch = raw_data[:batch_size]
                                    yield raw_data_batch
                                    raw_data = raw_data[batch_size:]
                                    if len(raw_data) == 0:
                                        break
                        else:
                            yield validate_result(result)
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
