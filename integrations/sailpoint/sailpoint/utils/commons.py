from sailpoint.utils.logging import Logger
from sailpoint.utils.pagination import PaginatedResponse, PaginatorProtocol
from functools import wraps
from dataclasses import dataclass
import time
from typing import Any, Callable, Coroutine


@dataclass
class BaseConfig:
    # help you configure anything configurable;
    pass


@dataclass
class Config:
    # application-wide configuration settings
    log_path: str


def paginate_response(
    *, paginator: PaginatorProtocol, response: Any
) -> PaginatedResponse:
    """
    Returns paginated response using the provided paginator strategy
    """
    items: list[dict] = response.json() if hasattr(response, "json") else response
    headers = getattr(response, "headers", {})
    total = int(headers.get("X-Total-Count", len(items)))

    return paginator.get_paginated_response(data=items, total=total)


async def paginated_response(
    *, paginator: PaginatorProtocol, response: Any
) -> PaginatedResponse:
    """
    Returns paginated response using the provided paginator strategy
    """
    if hasattr(response, "json"):
        items: list[dict] = await response.json()
    else:
        items = response

    headers = getattr(response, "headers", {})
    total = int(headers.get("X-Total-Count", len(items)))

    return paginator.get_paginated_response(data=items, total=total)


def benchmark_latency(
    func: Callable[..., Coroutine[Any, Any, Any]], *args, **kwargs
) -> Any:
    """
    Benchmarks the latency of an async function
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            response = await func(*args, **kwargs)

            if hasattr(response, "status_code") and response.status_code not in (
                200,
                201,
            ):
                # don't benchmark failed requests
                pass
            return response
        except Exception as e:
            Logger.log_error(
                message="Request failed during benchmarked call",
                error=e,
                context={"func": func.__name__},
            )
            raise
        finally:
            end_time = time.perf_counter()
            latency_ms = round((end_time - start_time) * 1000, 2)
            Logger._get_logger().info(
                f"[Latency] {func.__name__} took {latency_ms} ms",
                extra={"origin": "latency_benchmark", "latency_ms": latency_ms},
            )

    return wrapper
