from gcp_core.helpers.retry.async_retry import async_generator_retry
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from aiolimiter import AsyncLimiter
from typing import Any, Optional, Callable
from loguru import logger

DEFAULT_REQUEST_TIMEOUT: float = 120


@async_generator_retry
async def paginated_query(
    client: Any,
    method: str,
    request: dict[str, Any],
    parse_fn: Callable[..., Any],
    rate_limiter: Optional[AsyncLimiter] = None,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    General function to handle paginated requests with rate limiting.

    :param client: The client object to use for the request.
    :param method: The method to call on the client object.
    :param request: The request to send to the method.
    :param parse_fn: The function to parse the response. This must be a nullary function - apply arguments with `functools.partial` if needed.
    :param rate_limiter: The rate limiter to use for the request. Optional, defaults to None.
    :param timeout: The timeout for the request. Defaults to 120 seconds.
    :return: An async generator that yields the parsed items.
    """
    page = 0
    page_token = None

    if rate_limiter:
        logger.info(
            f"Executing {method} request: {request}. Current rate limit: {rate_limiter.max_rate} requests per {rate_limiter.time_period} seconds."
        )
    while True:
        if page_token:
            request["page_token"] = page_token

        if rate_limiter:
            logger.debug(f"Rate limiting enabled for `{method}`")
            async with rate_limiter:
                response = await getattr(client, method)(request, timeout=timeout)
        else:
            response = await getattr(client, method)(
                request,
                timeout=DEFAULT_REQUEST_TIMEOUT,
            )

        items = parse_fn(response)
        if items:
            page += 1
            logger.info(
                f"Found {len(items)} items on page {page} for `{method}` with request: {request}"
            )
            yield items
        else:
            logger.info(
                f"No items found on page {page} for `{method}` with request: {request}"
            )

        page_token = getattr(response, "next_page_token", None)
        if not page_token:
            logger.info(
                f"No more pages left for `{method}`. Query complete after {page} pages."
            )
            break
