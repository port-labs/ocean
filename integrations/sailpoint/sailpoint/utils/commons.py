from sailpoint.utils.logging import Logger
from sailpoint.utils.pagination import PaginatedResponse, PaginatorProtocol
from functools import wraps
from dataclasses import dataclass
import time
from typing import Any


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


async def benchmark_latency(func, *args, **kwargs):
    """
    Benchmarks the latency of an async function
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        @wraps(func)
        async def inner_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            response = None

            try:
                response = await func(*args, **kwargs)

                if response.status_code not in (200, 201):
                    # don't benchmark failed requests
                    pass

            except Exception as e:
                response_status_code = getattr(response, "status_code", None)
                Logger.log_error(
                    message=f"Request failed with status code {response_status_code}",
                    error=e,
                    _context={"response": response},
                )
                raise e

            end_time = time.perf_counter()
            latency_ms = round((end_time - start_time) * 1000, 2)
            return {"latency_ms": latency_ms, "response": response}

        return await inner_wrapper(*args, **kwargs)

    return await wrapper(*args, **kwargs)
