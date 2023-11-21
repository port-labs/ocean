from functools import wraps
from typing import Callable, Any

import httpx
from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.helpers.retry import RetryTransport

_http_client: LocalStack[httpx.AsyncClient] = LocalStack()


def _get_http_client_context() -> httpx.AsyncClient:
    client = _http_client.top
    if client is None:
        client = httpx.AsyncClient(
            transport=RetryTransport(
                httpx.AsyncHTTPTransport(),
                logger=logger,
            )
        )
        _http_client.push(client)

    return client


async_client: httpx.AsyncClient = LocalProxy(lambda: _get_http_client_context())  # type: ignore


def handle_status_code(
    response: httpx.Response, should_raise: bool = True, should_log: bool = True
) -> None:
    if should_log and response.is_error:
        logger.error(
            f"Request failed with status code: {response.status_code}, Error: {response.text}"
        )
    if should_raise:
        response.raise_for_status()


def retry_on_http_status(
    status_code: int,
    max_retries: int = 2,
    verbose: bool = True,
) -> Callable[..., Callable[..., Any]]:
    """
    Decorator to retry a function if it raises a httpx.HTTPStatusError with a given status code
    :param status_code: The status code to retry on
    :param max_retries: The maximum number of retries
    :param verbose: Whether to log retries
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:  # type: ignore
            retries = 0
            while retries < max_retries:
                try:
                    result = await func(*args, **kwargs)
                    return result
                except httpx.HTTPStatusError as err:
                    if err.response.status_code == status_code:
                        retries += 1
                        if retries < max_retries:
                            if verbose:
                                logger.warning(
                                    f"Retrying {func.__name__} after {status_code} error. Retry {retries}/{max_retries}"
                                )
                        else:
                            logger.error(
                                f"Reached max retries {max_retries} for {func.__name__} after {status_code} error"
                            )
                            raise
                    else:
                        raise

        return wrapper

    return decorator
