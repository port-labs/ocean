import asyncio
import json
import time
from functools import wraps
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from loguru import logger
from port_ocean.context import resource
import port_ocean.context.event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@dataclass
class BaseStats:
    error_count: int = 0
    duration: float = 0.0
    object_count: int = 0


@dataclass
class ApiStats(BaseStats):
    rate_limit_wait: float = 0.0
    requests: dict[str, int] = field(default_factory=dict)


@dataclass
class ExtractStats(ApiStats):
    pass


@dataclass
class TransformStats(BaseStats):
    failed_count: int = 0
    input_count: int = 0


@dataclass
class LoadStats(ApiStats):
    upserted: int = 0
    deleted: int = 0


@dataclass
class MetricsData:
    extract: ExtractStats = field(default_factory=ExtractStats)
    transform: TransformStats = field(default_factory=TransformStats)
    load: LoadStats = field(default_factory=LoadStats)


@dataclass
class KindsMetricsData:
    metrics: dict[str, MetricsData] = field(default_factory=dict)


class MetricFieldType:
    UPSERTED = "upserted"
    DELETED = "deleted"
    FAILED = "failed_count"
    REQUEST = "requests"
    RATE_LIMIT = "rate_limit_wait"
    OBJECT_COUNT = "object_count"
    DURATION = "duration"
    ERROR_COUNT = "error_count"
    INPUT_COUNT = "input_count"


class MetricType:
    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"


class MetricAggregator:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.metrics: KindsMetricsData = KindsMetricsData()

    async def get_metrics(self) -> dict[str, MetricsData]:
        return self.metrics.metrics

    async def get_metric(self) -> TransformStats | LoadStats | ExtractStats | None:
        phase = port_ocean.context.event.event.attributes.get("phase", None)
        if not phase:
            return None

        metric = self.metrics.metrics.get(resource.resource.kind)
        if not metric:
            self.metrics.metrics[resource.resource.kind] = MetricsData()

        return getattr(self.metrics.metrics.get(resource.resource.kind), phase)

    async def increment_field(self, field: str, amount: int | float = 1) -> None:
        metric = await self.get_metric()
        async with self._lock:
            val = getattr(metric, field)
            metric.__setattr__(field, val + amount)

    async def increment_status(self, status_code: str) -> None:
        metric = await self.get_metric()
        if metric is None or not isinstance(metric, ApiStats):
            return None
        async with self._lock:

            status = metric.requests.get(status_code)
            if not status:
                metric.requests[status_code] = 0
            metric.requests[status_code] = metric.requests.get(status_code, 0) + 1

    async def flush(self) -> None:
        async with self._lock:
            metric_dict = asdict(self.metrics)
            logger.info(f"integration metrics {json.dumps(metric_dict)}")
        await self.reset()

    async def reset(self) -> None:
        async with self._lock:
            self.metrics = KindsMetricsData()


async def timed_generator(
    generator: ASYNC_GENERATOR_RESYNC_TYPE,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not port_ocean.context.event.event.should_record_metrics:
        async for items in generator:
            yield items
    async with port_ocean.context.event.event_context(
        port_ocean.context.event.EventType.METRIC, attributes={"phase": "extract"}
    ):
        while True:
            try:
                start = time.monotonic()
                items = await anext(generator)
                end = time.monotonic()
                duration = end - start
                await port_ocean.context.event.event.increment_metric(
                    MetricFieldType.DURATION, duration
                )
                await port_ocean.context.event.event.increment_metric(
                    MetricFieldType.OBJECT_COUNT, len(items)
                )

                yield items
            except Exception:
                break


def metric(phase: str | None = None, should_capture_time: bool = True) -> Any:
    def decorator(func: Callable[..., Any]) -> Any:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: dict[Any, Any]) -> Any:
            if not port_ocean.context.event.event.should_record_metrics:
                return await func(*args, **kwargs)
            if not phase:
                _phase = port_ocean.context.event.event.attributes.get("phase")
            async with port_ocean.context.event.event_context(
                port_ocean.context.event.EventType.METRIC,
                attributes={"phase": phase or _phase},
            ):
                res = None
                start = time.monotonic()
                res = await func(*args, **kwargs)
                if should_capture_time:
                    end = time.monotonic()
                    duration = end - start
                    await port_ocean.context.event.event.increment_metric(
                        MetricFieldType.DURATION, duration
                    )
                return res

        return wrapper

    return decorator
