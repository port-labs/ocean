"""
HTTP Server Integration Main Module

Main entry point for the HTTP server integration with resync handlers.
"""

import re
from typing import cast, List
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import init_client
from http_server.overrides import (
    HttpServerResourceConfig,
    HttpServerSelector,
    ApiPathParameter,
)


@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync resources from HTTP endpoints - kind is the endpoint path"""
    logger.info(f"Starting resync for kind (endpoint): {kind}")
    http_client = init_client()
    resource_config = cast(HttpServerResourceConfig, event.resource_config)

    selector = resource_config.selector

    # The kind IS the endpoint path (e.g., "/api/v1/users")
    # Check if endpoint has path parameters that need resolution
    endpoints = await resolve_dynamic_endpoints(selector, kind)

    logger.info(f"Resolved {len(endpoints)} endpoints to call for kind: {kind}")

    # Extract method, query_params, headers, data_path from selector
    method = getattr(selector, "method", "GET")
    query_params = getattr(selector, "query_params", None) or {}
    headers = getattr(selector, "headers", None) or {}
    data_path = getattr(selector, "data_path", None)

    # Call each resolved endpoint
    for endpoint in endpoints:
        logger.info(f"Fetching data from: {method} {endpoint}")

        try:
            async for batch in http_client.fetch_paginated_data(
                endpoint=endpoint,
                method=method,
                query_params=query_params,
                headers=headers,
            ):
                logger.info(f"Received {len(batch)} records from {endpoint}")

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
                                processed_batch.extend(extracted_data)
                            elif extracted_data is not None:
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

    # Note: No need to close Ocean's singleton HTTP client


async def resolve_dynamic_endpoints(
    selector: HttpServerSelector, kind: str
) -> List[str]:
    """Resolve dynamic endpoints using Ocean's Port client with validation

    Args:
        selector: The resource selector configuration
        kind: The endpoint path (e.g., "/api/v1/users" or "/api/v1/teams/{team_id}")

    Returns:
        List of resolved endpoint URLs
    """
    if not kind:
        logger.error("Kind (endpoint) is empty")
        return []

    # Get path_parameters from selector if they exist
    path_parameters = getattr(selector, "path_parameters", None) or {}

    # Find path parameters in endpoint template
    param_names = re.findall(r"\{(\w+)\}", kind)

    if not param_names:
        return [kind]

    # Validate that all parameters are configured
    missing_params = [name for name in param_names if name not in path_parameters]
    if missing_params:
        logger.error(f"Missing configuration for path parameters: {missing_params}")
        return [kind]

    # For now, handle single parameter (can extend for multiple later)
    if len(param_names) > 1:
        logger.warning(
            f"Multiple path parameters detected: {param_names}. "
            "Only the first parameter will be resolved."
        )

    param_name = param_names[0]
    param_config = path_parameters[param_name]

    # Query API for parameter values
    parameter_values = await query_api_for_parameters(param_config)

    if not parameter_values:
        logger.error(f"No valid values found for path parameter '{param_name}'")
        return []

    # Generate resolved endpoints
    resolved_endpoints = []
    for value in parameter_values:
        resolved_endpoint = kind.replace(f"{{{param_name}}}", str(value))
        resolved_endpoints.append(resolved_endpoint)

    logger.info(
        f"Resolved {len(resolved_endpoints)} endpoints from parameter '{param_name}'"
    )
    return resolved_endpoints


async def query_api_for_parameters(param_config: ApiPathParameter) -> List[str]:
    """Query an API to get values for a path parameter"""
    http_client = init_client()

    logger.info(f"Querying API for parameter values from {param_config.endpoint}")

    try:
        async for batch in http_client.fetch_paginated_data(
            endpoint=param_config.endpoint,
            method=param_config.method,
            query_params=param_config.query_params,
            headers=param_config.headers,
        ):
            # Extract values using JQ expression
            values = []
            for item in batch:
                try:
                    # Use Ocean's built-in JQ processor
                    extracted_value = await ocean.app.integration.entity_processor._search(  # type: ignore[attr-defined]
                        item, param_config.field
                    )
                    if extracted_value is not None:
                        # Apply optional filter
                        if param_config.filter:
                            filter_result = await ocean.app.integration.entity_processor._search(  # type: ignore[attr-defined]
                                item, param_config.filter
                            )
                            if filter_result is True:
                                values.append(str(extracted_value))
                        else:
                            values.append(str(extracted_value))
                except Exception as e:
                    logger.warning(f"Error extracting value from item: {e}")
                    continue

            if values:
                return values

    except Exception as e:
        logger.error(
            f"Error querying API for parameter values from {param_config.endpoint}: {str(e)}"
        )

    return []
