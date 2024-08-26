from gcp_core.search.helpers.retry.async_retry import async_generator_retry
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from aiolimiter import AsyncLimiter
from typing import Any, Optional
from loguru import logger
import asyncio

REQUEST_TIMEOUT = 120.0
MAXIMUM_CONCURRENT_REQUEST = 100
semaphore = asyncio.BoundedSemaphore(MAXIMUM_CONCURRENT_REQUEST)


@async_generator_retry
async def paginated_query(
    client: Any,
    method: str,
    request: dict[str, Any],
    parse_fn: Any,
    rate_limiter: Optional[AsyncLimiter] = None,
    *args: Any,
    **kwargs: Any,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    General function to handle paginated requests with rate limiting.
    """
    page = 0
    page_token = None

    while True:
        if page_token:
            request["page_token"] = page_token

        if rate_limiter:
            logger.debug(f"Rate limiting enabled for `{method}`")
            async with rate_limiter:
                response = await getattr(client, method)(
                    request,
                    timeout=kwargs.get("timeout", REQUEST_TIMEOUT),
                )
        else:
            response = await getattr(client, method)(
                request,
                timeout=REQUEST_TIMEOUT,
            )

        items = parse_fn(response)
        if items:
            page += 1
            logger.info(
                f"Found {len(items)} items on page {page} for `{method}` with request: {request}"
            )
            yield items
        else:
            logger.warning(
                f"No items found on page {page} for `{method}` with request: {request}"
            )

        page_token = getattr(response, "next_page_token", None)
        if not page_token:
            logger.info(
                f"No more pages left for `{method}`. Query complete after {page} pages."
            )
            break
