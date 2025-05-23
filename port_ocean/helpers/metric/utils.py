from functools import wraps
import time
from typing import Any, Callable

from port_ocean.context.ocean import ocean
from port_ocean.helpers.metric.metric import MetricType


def TimeMetric(phase: str) -> Any:
    def decorator(func: Callable[..., Any]) -> Any:

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: dict[Any, Any]) -> Any:
            start = time.monotonic()
            res = await func(*args, **kwargs)
            end = time.monotonic()
            duration = end - start
            ocean.metrics.inc_metric(
                name=MetricType.DURATION_NAME,
                labels=[ocean.metrics.current_resource_kind(), phase],
                value=duration,
            )

            return res

        return wrapper

    return decorator
