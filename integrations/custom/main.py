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
from http_server.helpers.endpoint_resolver import (
    resolve_dynamic_endpoints,
    resolve_dynamic_query_params,
)
from http_server.helpers.endpoint_cache import (
    get_endpoint_cache,
    initialize_endpoint_cache,
    clear_endpoint_cache,
)
from http_server.helpers.utils import (
    extract_and_enrich_batch,
    process_endpoints_concurrently,
    DEFAULT_CONCURRENCY_LIMIT,
)


@ocean.on_resync_start()
async def on_resync_start() -> None:
    """Pre-analyze resource configs and initialize the endpoint response cache."""
    app_config = event.port_app_config
    resources = [cast(HttpServerResourceConfig, r) for r in app_config.resources]
    initialize_endpoint_cache(resources)


@ocean.on_resync_complete()
async def on_resync_complete() -> None:
    """Clean up cached endpoint response files after resync."""
    clear_endpoint_cache()


def _raw_fetch(
    http_client: HttpServerClient,
    endpoint: str,
    method: str,
    query_params: Dict[str, Any],
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]],
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Return an async generator over raw paginated API pages."""
    return http_client.fetch_paginated_data(
        endpoint=endpoint,
        method=method,
        query_params=query_params,
        headers=headers,
        body=body,
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

    cache = get_endpoint_cache()
    raw_source: AsyncGenerator[List[Dict[str, Any]], None]
    if cache is not None:
        raw_source = cache.get_or_fetch(
            endpoint=endpoint,
            method=method,
            query_params=query_params,
            headers=headers,
            body=body,
            fetch_fn=functools.partial(
                _raw_fetch, http_client, endpoint, method, query_params, headers, body
            ),
        )
    else:
        raw_source = _raw_fetch(
            http_client, endpoint, method, query_params, headers, body
        )

    try:
        async for batch in raw_source:
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
    query_params = getattr(selector, "query_params", None)
    dynamic_query_param = getattr(selector, "dynamic_query_param", None)
    headers = getattr(selector, "headers", None) or {}
    body = getattr(selector, "body", None)
    data_path = getattr(selector, "data_path", None) or "."

    async for resolved_query_params in resolve_dynamic_query_params(
        query_params, dynamic_query_param
    ):
        async for endpoint_batch in resolve_dynamic_endpoints(selector, kind):
            fetch_fn = functools.partial(
                fetch_endpoint_data,
                http_client=http_client,
                method=method,
                query_params=resolved_query_params,
                headers=headers,
                body=body,
                data_path=data_path,
            )

            async for batch in process_endpoints_concurrently(
                endpoints=endpoint_batch,
                fetch_fn=fetch_fn,
                concurrency_limit=DEFAULT_CONCURRENCY_LIMIT,
            ):
                yield batch
