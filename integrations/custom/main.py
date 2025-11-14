"""
HTTP Server Integration Main Module

Main entry point for the HTTP server integration with resync handlers.
"""

from typing import cast
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import init_client
from http_server.overrides import HttpServerResourceConfig
from http_server.helpers.endpoint_resolver import resolve_dynamic_endpoints


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync resources from HTTP endpoints - kind is the endpoint path"""
    logger.info(f"Starting resync for kind (endpoint): {kind}")
    http_client = init_client()
    resource_config = cast(HttpServerResourceConfig, event.resource_config)

    selector = resource_config.selector

    # The kind IS the endpoint path (e.g., "/api/v1/users")
    # Check if endpoint has path parameters that need resolution
    # Returns list of tuples: (endpoint_url, {param_name: param_value})
    endpoints = await resolve_dynamic_endpoints(selector, kind)

    logger.info(f"Resolved {len(endpoints)} endpoints to call for kind: {kind}")

    # Extract method, query_params, headers from selector
    method = getattr(selector, "method", "GET")
    query_params = getattr(selector, "query_params", None) or {}
    headers = getattr(selector, "headers", None) or {}

    # Call each resolved endpoint
    for endpoint, path_params in endpoints:
        logger.info(f"Fetching data from: {method} {endpoint}")
        
        # Extract data_path per endpoint (may be auto-detected from first batch)
        data_path = getattr(selector, "data_path", None)

        try:
            async for batch in http_client.fetch_paginated_data(
                endpoint=endpoint,
                method=method,
                query_params=query_params,
                headers=headers,
            ):
                logger.info(f"Received {len(batch)} records from {endpoint}")

                # Auto-detect list responses and default data_path to '.' if missing
                # This fixes the issue where direct list responses fail validation
                # Pagination handlers yield [response_data], so batch[0] is the raw response
                if data_path is None and batch:
                    response_data = batch[0]
                    if isinstance(response_data, list):
                        # Auto-detect direct list responses
                        data_path = "."
                        logger.info("Auto-detected list response, using data_path: '.'")
                    else:
                        # Not a list and no data_path specified - log error and continue
                        # Let Ocean's validation handle it downstream
                        logger.error(
                            f"Response from {endpoint} is not a list and 'data_path' is not specified. "
                            f"Yielding response as-is. If mapping fails, please specify 'data_path' in your selector "
                            f"(e.g., data_path: '.data'). Response type: {type(response_data).__name__}"
                        )
                        # Continue without setting data_path - will yield batch as-is

                # If data_path is specified, extract the array from each response
                if data_path:
                    processed_batch = []
                    for item in batch:
                        try:
                            # Use Ocean's built-in JQ processor
                            extracted_data = await ocean.app.integration.entity_processor._search(  # type: ignore[attr-defined]
                                item, data_path
                            )
                            if isinstance(extracted_data, list):
                                # Inject path parameters into each extracted item
                                for entity in extracted_data:
                                    if isinstance(entity, dict) and path_params:
                                        for (
                                            param_name,
                                            param_value,
                                        ) in path_params.items():
                                            entity[f"__{param_name}"] = param_value
                                processed_batch.extend(extracted_data)
                            elif extracted_data is not None:
                                # Inject path parameters for single item
                                if isinstance(extracted_data, dict) and path_params:
                                    for param_name, param_value in path_params.items():
                                        extracted_data[f"__{param_name}"] = param_value
                                processed_batch.append(extracted_data)
                        except Exception as e:
                            logger.error(
                                f"Error extracting data with JQ path '{data_path}': {e}"
                            )
                            continue

                    if processed_batch:
                        logger.info(
                            f"Extracted {len(processed_batch)} items using data_path: {data_path}"
                        )
                        yield processed_batch
                else:
                    yield batch

        except Exception as e:
            logger.error(f"Error fetching data from {endpoint}: {str(e)}")
            continue
