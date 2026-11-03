import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Awaitable, Callable, Generator

from loguru import logger

from port_ocean.clients.dsp.lifecycle_http import (
    _lifecycle_http_client as _dsp_lifecycle_http_client,
)
from port_ocean.clients.port.utils import _http_client as _port_http_client
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import (
    ASYNC_GENERATOR_RESYNC_TYPE,
    RAW_RESULT,
    RESYNC_RESULT,
)
from port_ocean.core.utils.utils import validate_result
from port_ocean.exceptions.core import (
    DSPProcessingUnavailableException,
    RawObjectValidationException,
    OceanAbortException,
    KindNotImplementedException,
)
from port_ocean.helpers.metric.metric import MetricType, MetricPhase
from port_ocean.helpers.monitor.monitor import get_monitor
from port_ocean.utils.async_http import _http_client
from port_ocean.core.models import (
    IntegrationFeatureFlag,
    LakehouseDataEntry,
    LakehouseDataEntryBatch,
    LakehouseDataEntryMetadata,
    LakehouseEventType,
    LakehouseOperation,
)


def collect_export_env_variables(
    variable_names: list[str],
) -> dict[str, str | None] | None:
    """Collect values for explicitly requested environment variable names."""
    if not variable_names:
        return None
    return {name: os.environ.get(name) for name in variable_names}


def build_lakehouse_data_entry(
    *,
    items: list[Any],
    metadata: LakehouseDataEntryMetadata,
    export_env_variables: list[str],
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
) -> LakehouseDataEntry:
    """Build a lakehouse data entry, collecting env vars for this bulk."""
    entry: LakehouseDataEntry = {
        "request": request or {},
        "response": response or {},
        "metadata": metadata,
        "items": items,
    }
    environment_data = collect_export_env_variables(export_env_variables)
    if environment_data is not None:
        entry["environment_data"] = environment_data
    return entry


def build_live_event_data_entry(
    *,
    resource: ResourceConfig,
    resource_index: int,
    items: list[Any],
    operation: LakehouseOperation,
) -> LakehouseDataEntry:
    return build_lakehouse_data_entry(
        items=items,
        metadata=LakehouseDataEntryMetadata(
            operation=operation,
            resource_index=resource_index,
            extraction_timestamp=int(datetime.now().timestamp() * 1000),
            selector_hash=selector_hash_from_resource(resource),
        ),
        export_env_variables=resource.selector.export_env_variables,
    )


async def send_raw_live_event(
    *,
    event_id: str,
    kind: str,
    resync_start_time: datetime | None,
    data_entries: list[LakehouseDataEntry],
) -> None:
    """Hand raw live-event data to the data-source-processor through the lakehouse.

    Upserted and deleted items of one event and kind go in a single POST so the
    lakehouse can correlate them under one event id.
    """
    if not data_entries:
        return
    logger.debug(
        f"Sending {len(data_entries)} live event data entries to lakehouse",
        event_id=event_id,
        kind=kind,
    )
    await ocean.port_client.post_integration_raw_data_batch(
        event_id,
        LakehouseDataEntryBatch(
            event_id=event_id,
            type=LakehouseEventType.LIVE_EVENT.value,
            kind=kind,
            event_type=LakehouseEventType.LIVE_EVENT,
            resync_start_time=resync_start_time,
            extraction_timestamp=int(datetime.now().timestamp() * 1000),
            data=data_entries,
        ),
    )


def selector_query_from_resource(resource: ResourceConfig) -> str | None:
    query = getattr(getattr(resource, "selector", None), "query", None)
    if not isinstance(query, str):
        return None

    trimmed = query.strip()
    return trimmed if trimmed else None


def selector_hash_from_selector(selector: str) -> str:
    return hashlib.sha256(selector.encode("utf-8")).hexdigest()


def _selector_without_query(resource: ResourceConfig) -> dict[str, Any] | None:
    selector = getattr(resource, "selector", None)
    if selector is None:
        return None

    if hasattr(selector, "dict"):
        selector_payload = selector.dict(
            by_alias=True, exclude_none=True, exclude_unset=True
        )
    elif isinstance(selector, dict):
        selector_payload = dict(selector)
    else:
        selector_payload = dict(getattr(selector, "__dict__", {}))

    selector_payload.pop("query", None)
    return selector_payload


def selector_hash_from_resource(resource: ResourceConfig) -> str | None:
    selector_without_query = _selector_without_query(resource)
    if selector_without_query is None:
        return None

    normalized_selector = json.dumps(
        selector_without_query, sort_keys=True, separators=(",", ":")
    )
    return selector_hash_from_selector(normalized_selector)


DSP_REQUIRED_FEATURE_FLAGS = (
    IntegrationFeatureFlag.LAKEHOUSE_ELIGIBLE,
    IntegrationFeatureFlag.DATA_SOURCE_PROCESSOR_ENABLED,
)


async def ensure_dsp_processing_available() -> None:
    """Fail fast when the organization cannot process raw data through the DSP.

    The data-source-processor is the only processing mode: Ocean extracts raw data and
    hands it off, so without the lakehouse and the DSP feature flags nothing would reach Port.
    """
    if not ocean.config.lakehouse_enabled:
        raise DSPProcessingUnavailableException(
            "OCEAN__LAKEHOUSE_ENABLED=false is no longer supported: raw data is processed "
            "exclusively by the data-source-processor through the lakehouse"
        )
    flags = await ocean.port_client.get_organization_feature_flags()
    missing_flags = [flag for flag in DSP_REQUIRED_FEATURE_FLAGS if flag not in flags]
    if missing_flags:
        raise DSPProcessingUnavailableException(
            "The organization is missing the feature flags required for data-source-processor "
            f"processing: {', '.join(missing_flags)}"
        )


async def is_live_event_payload_logging_enabled() -> bool:
    """Return whether full live-event payload logging is enabled.

    Requires both the integration setting
    ``OCEAN__LIVE_EVENTS__PAYLOAD_LOGGING_ENABLED`` (default false) and the
    organization feature flag ``LIVE_EVENTS_PAYLOAD_LOGGING_ENABLED``. When the
    integration setting is false, Port is not queried for feature flags.
    """
    try:
        if not ocean.config.live_events.payload_logging_enabled:
            return False
        flags = await ocean.port_client.get_organization_feature_flags(
            should_raise=False,
            should_log=False,
        )
        return IntegrationFeatureFlag.LIVE_EVENTS_PAYLOAD_LOGGING_ENABLED in flags
    except Exception as e:
        logger.bind(local_only=True).warning(
            f"Failed to check live event payload logging settings, assuming disabled: {e}"
        )
        return False


async def is_redis_live_events_enabled() -> bool:
    """Check if live events should be consumed from a Redis stream.

    Gated by the integration-level
    ``OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED`` setting (default false)
    and whether the organization is blocked.
    Errors are swallowed so this never blocks core flows.

    Returns:
        bool: True when Redis stream consumption is enabled, False otherwise.
    """
    try:
        if not ocean.config.live_events.is_redis_stream_consumer_enabled:
            return False
        if await ocean.port_client.is_organization_blocked():
            return False
        return True
    except Exception as e:
        logger.bind(local_only=True).warning(
            f"Failed to check Redis live events settings, assuming disabled: {e}"
        )
        return False


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
    except OceanAbortException:
        raise
    except Exception as error:
        err_msg = f"Failed to execute resync function, error: {error}"
        logger.exception(err_msg)
        raise OceanAbortException(err_msg) from error


async def resync_function_wrapper(
    fn: Callable[[str], Awaitable[RAW_RESULT]],
    kind: str,
    send_raw_data_examples_amount: int = 0,
) -> RAW_RESULT:
    with resync_error_handling():
        results = validate_result(await fn(kind))
        await send_raw_data_examples(results, kind, send_raw_data_examples_amount)
        return results


async def send_raw_data_examples(result: RAW_RESULT, kind: str, amount: int) -> int:
    if amount <= 0 or not result:
        return 0

    examples_to_send = [item.copy() for item in result[:amount]]
    try:
        await ocean.port_client.ingest_integration_kind_examples(
            kind, examples_to_send, should_log=False
        )
        return len(examples_to_send)
    except Exception as ex:
        logger.warning(
            f"Failed to send raw data example {ex}",
            exc_info=True,
        )
        return 0


async def resync_generator_wrapper(
    fn: Callable[[str], ASYNC_GENERATOR_RESYNC_TYPE],
    kind: str,
    send_raw_data_examples_amount: int = 0,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    generator = fn(kind)
    errors = []
    remaining_examples_to_send = send_raw_data_examples_amount
    try:
        while True:
            try:
                with resync_error_handling():
                    result = validate_result(await anext(generator))
                    sent_examples = await send_raw_data_examples(
                        result, kind, remaining_examples_to_send
                    )
                    remaining_examples_to_send = max(
                        0, remaining_examples_to_send - sent_examples
                    )

                    yield result

            except OceanAbortException as error:
                errors.append(error)
                ocean.metrics.inc_metric(
                    name=MetricType.OBJECT_COUNT_NAME,
                    labels=[
                        ocean.metrics.current_resource_kind(),
                        MetricPhase.EXTRACT,
                        MetricPhase.ExtractResult.FAILED,
                    ],
                    value=1,
                )
    except StopAsyncIteration:
        if errors:
            raise ExceptionGroup(
                "At least one of the resync generator iterations failed", errors
            )


def unsupported_kind_response(
    kind: str, available_resync_kinds: list[str]
) -> tuple[RESYNC_RESULT, list[Exception]]:
    logger.error(f"Kind {kind} is not supported in this integration")
    return [], [KindNotImplementedException(kind, available_resync_kinds)]


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

    try:
        while _dsp_lifecycle_http_client.top is not None:
            _dsp_lifecycle_http_client.pop()
    except (RuntimeError, AttributeError):
        pass


def start_kind_tracking(kind: str) -> None:
    monitor = get_monitor()
    monitor.start_kind_tracking(kind)


def stop_kind_tracking(kind: str) -> None:
    monitor = get_monitor()
    monitor.stop_kind_tracking(kind)
    stats = monitor.get_kind_stats(kind)
    if stats.sample_count > 0:
        # Report CPU metrics
        ocean.metrics.set_metric(MetricType.CPU_MAX_NAME, [kind], stats.cpu.cpu_max)
        ocean.metrics.set_metric(
            MetricType.CPU_MEDIAN_NAME, [kind], stats.cpu.cpu_median
        )
        ocean.metrics.set_metric(MetricType.CPU_AVG_NAME, [kind], stats.cpu.cpu_avg)
        # Report memory metrics
        ocean.metrics.set_metric(
            MetricType.MEMORY_MAX_NAME, [kind], stats.memory.memory_max
        )
        ocean.metrics.set_metric(
            MetricType.MEMORY_MEDIAN_NAME,
            [kind],
            stats.memory.memory_median,
        )
        ocean.metrics.set_metric(
            MetricType.MEMORY_AVG_NAME, [kind], stats.memory.memory_avg
        )
        # Report latency metrics
        ocean.metrics.set_metric(
            MetricType.LATENCY_MAX_NAME,
            [kind],
            stats.latency.latency_max,
        )
        ocean.metrics.set_metric(
            MetricType.LATENCY_MEDIAN_NAME,
            [kind],
            stats.latency.latency_median,
        )
        ocean.metrics.set_metric(
            MetricType.LATENCY_AVG_NAME,
            [kind],
            stats.latency.latency_avg,
        )
    # Report response size metrics (always report, even if no requests)
    ocean.metrics.set_metric(
        MetricType.RESPONSE_SIZE_TOTAL_NAME,
        [kind],
        stats.response_size.response_size_total,
    )
    ocean.metrics.set_metric(
        MetricType.RESPONSE_SIZE_AVG_NAME,
        [kind],
        stats.response_size.response_size_avg,
    )
    ocean.metrics.set_metric(
        MetricType.RESPONSE_SIZE_MEDIAN_NAME,
        [kind],
        stats.response_size.response_size_median,
    )
    monitor.cleanup_kind_tracking(kind)
