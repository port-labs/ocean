"""
HTTP Server Integration Main Module

Main entry point for the HTTP server integration with resync handlers.
"""

import functools
from typing import cast, AsyncGenerator, Dict, List, Any, Optional

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import get_client
from http_server.overrides import HttpServerResourceConfig
from http_server.client import HttpServerClient
from http_server.helpers.endpoint_resolver import resolve_dynamic_endpoints
from http_server.helpers.utils import (
    extract_and_enrich_batch,
    process_endpoints_concurrently,
    DEFAULT_CONCURRENCY_LIMIT,
)


async def fetch_endpoint_data(
    endpoint: str,
    path_params: Dict[str, str],
    http_client: HttpServerClient,
    method: str,
    query_params: Dict[str, Any],
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
    data_path: str,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Fetch and process data from a single endpoint

    Args:
        endpoint: The endpoint URL to fetch data from
        path_params: Path parameters to inject into each entity
        http_client: The HTTP client instance for making requests
        method: HTTP method (GET, POST, etc.)
        query_params: Query parameters for the request
        headers: HTTP headers for the request
        body: Optional request body
        data_path: JQ path to extract data from response

    Yields:
        Batches of processed data from the endpoint
    """
    logger.info(f"Fetching data from: {method} {endpoint}")

    try:
        async for batch in http_client.fetch_paginated_data(
            endpoint=endpoint,
            method=method,
            query_params=query_params,
            headers=headers,
            body=body,
        ):
            logger.info(f"Received {len(batch)} records from {endpoint}")

            if data_path == "." and batch and not isinstance(batch[0], list):
                logger.warning(
                    f"Response from {endpoint} is not a list and 'data_path' is not specified. "
                    f"Yielding response as-is. If mapping fails, please specify 'data_path' in your selector "
                    f"(e.g., data_path: '.data'). Response type: {type(batch[0]).__name__}"
                )
                yield batch
                continue

            processed_batch = extract_and_enrich_batch(
                batch, data_path, path_params, endpoint
            )

            if processed_batch:
                logger.info(
                    f"Extracted {len(processed_batch)} items using data_path: {data_path}"
                )
                yield processed_batch

    except Exception as e:
        logger.error(f"Error fetching data from {endpoint}: {str(e)}")


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync resources from HTTP endpoints - kind is the endpoint path"""
    logger.info(f"Starting resync for kind (endpoint): {kind}")
    http_client = await get_client()
    resource_config = cast(HttpServerResourceConfig, event.resource_config)

    selector = resource_config.selector

    method = getattr(selector, "method", "GET")
    query_params = getattr(selector, "query_params", None) or {}
    headers = getattr(selector, "headers", None) or {}
    body = getattr(selector, "body", None)
    data_path = getattr(selector, "data_path", None) or "."

    fetch_fn = functools.partial(
        fetch_endpoint_data,
        http_client=http_client,
        method=method,
        query_params=query_params,
        headers=headers,
        body=body,
        data_path=data_path,
    )

    async for endpoint_batch in resolve_dynamic_endpoints(selector, kind):
        async for batch in process_endpoints_concurrently(
            endpoints=endpoint_batch,
            fetch_fn=fetch_fn,
            concurrency_limit=DEFAULT_CONCURRENCY_LIMIT,
        ):
            yield batch
