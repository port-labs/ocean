"""
Helper Utilities

Provides utility functions for the HTTP Server integration.
"""

import asyncio
import functools
from typing import (
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Any,
    Tuple,
)

from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from port_ocean.core.handlers.entity_processor.jq_entity_processor_sync import (
    JQEntityProcessorSync,
)

DEFAULT_CONCURRENCY_LIMIT = 10


def inject_path_params(
    data: Dict[str, Any], path_params: Dict[str, str]
) -> Dict[str, Any]:
    """Inject path parameters into entity data"""
    if isinstance(data, dict) and path_params:
        for param_name, param_value in path_params.items():
            data[f"__{param_name}"] = param_value
    return data


def extract_and_enrich_batch(
    batch: List[Dict[str, Any]],
    data_path: str,
    path_params: Dict[str, str],
    endpoint: str,
) -> List[Dict[str, Any]]:
    """Extract data using JQ path and inject path parameters

    Args:
        batch: Raw batch from API response
        data_path: JQ path to extract data
        path_params: Path parameters to inject into each entity
        endpoint: Endpoint URL for logging

    Returns:
        Processed and enriched batch
    """
    processed_items: List[Dict[str, Any]] = []

    for item in batch:
        try:
            extracted_data = JQEntityProcessorSync._search(item, data_path)

            if isinstance(extracted_data, list):
                for entity in extracted_data:
                    inject_path_params(entity, path_params)
                processed_items.extend(extracted_data)
            elif extracted_data is not None:
                inject_path_params(extracted_data, path_params)
                processed_items.append(extracted_data)

        except Exception as error:
            logger.error(
                f"Error extracting data with JQ path '{data_path}' from {endpoint}: {error}"
            )
            continue

    return processed_items


async def process_endpoints_concurrently(
    endpoints: List[Tuple[str, Dict[str, str]]],
    fetch_fn: Callable[
        [str, Dict[str, str]], AsyncGenerator[List[Dict[str, Any]], None]
    ],
    concurrency_limit: int = DEFAULT_CONCURRENCY_LIMIT,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Process multiple endpoints concurrently with bounded concurrency

    Args:
        endpoints: List of (endpoint_url, path_params) tuples to process
        fetch_fn: Async generator function that fetches data for an endpoint
        concurrency_limit: Maximum number of concurrent requests

    Yields:
        Batches of processed data from all endpoints as they complete
    """
    if not endpoints:
        return

    semaphore = asyncio.BoundedSemaphore(concurrency_limit)

    logger.info(
        f"Processing {len(endpoints)} endpoints with concurrency limit: {concurrency_limit}"
    )

    tasks = [
        semaphore_async_iterator(
            semaphore,
            functools.partial(fetch_fn, endpoint, path_params),
        )
        for endpoint, path_params in endpoints
    ]

    async for batch in stream_async_iterators_tasks(*tasks):
        yield batch
