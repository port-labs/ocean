from functools import wraps
import time
from typing import Any, Callable

import port_ocean.context.ocean
from port_ocean.helpers.metric.metric import MetricType


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
            ).set(duration)

            return res

        return wrapper

    return decorator
