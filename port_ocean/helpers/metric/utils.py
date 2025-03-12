from functools import wraps
import time
from typing import Any, Callable

import port_ocean.context.ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.helpers.metric.metric import MetricPhase, MetricType


async def timed_generator(
    generator: ASYNC_GENERATOR_RESYNC_TYPE,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if not port_ocean.context.ocean.ocean.metrics.enabled:
        async for items in generator:
            yield items
    while True:
        try:
            start = time.monotonic()
            items = await anext(generator)
            end = time.monotonic()
            duration = end - start
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.DURATION[0], [MetricPhase.EXTRACT]
            ).inc(duration)
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.OBJECT_COUNT[0], [MetricPhase.EXTRACT]
            ).inc(len(items))
            yield items
        except StopAsyncIteration:
            break
        except Exception as e:
            raise e


def TimeMetric(phase: str) -> Any:
    def decorator(func: Callable[..., Any]) -> Any:

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: dict[Any, Any]) -> Any:
            if not port_ocean.context.ocean.ocean.metrics.enabled:
                return await func(*args, **kwargs)
            start = time.monotonic()
            res = await func(*args, **kwargs)
            end = time.monotonic()
            duration = end - start
            port_ocean.context.ocean.ocean.metrics.get_metric(
                MetricType.DURATION[0], [phase]
            ).inc(duration)

            return res

        return wrapper

    return decorator
