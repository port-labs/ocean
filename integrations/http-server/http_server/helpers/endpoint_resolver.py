"""
Endpoint Resolution Module

Handles dynamic endpoint resolution for path parameters.
"""

import re
from typing import List, Dict, Any
from loguru import logger

from port_ocean.context.ocean import ocean
from http_server.overrides import HttpServerSelector, ApiPathParameter
from initialize_client import init_client


def extract_path_parameters(endpoint: str) -> List[str]:
    """Extract parameter names from endpoint template

    Args:
        endpoint: Endpoint template (e.g., "/api/v1/teams/{team_id}/members")

    Returns:
        List of parameter names found (e.g., ["team_id"])
    """
    return re.findall(r"\{(\w+)\}", endpoint)


def validate_endpoint_parameters(
    param_names: List[str], path_parameters: Dict[str, Any]
) -> List[str]:
    """Validate that all required parameters are configured

    Args:
        param_names: List of parameter names from endpoint template
        path_parameters: Configuration dict for path parameters

    Returns:
        List of missing parameter names (empty list if all valid)
    """
    return [name for name in param_names if name not in path_parameters]


def generate_resolved_endpoints(
    endpoint_template: str, param_name: str, param_values: List[str]
) -> List[tuple[str, Dict[str, str]]]:
    """Generate resolved endpoints with parameter values

    Args:
        endpoint_template: Template with parameter placeholder (e.g., "/api/teams/{team_id}")
        param_name: Name of parameter to replace (e.g., "team_id")
        param_values: List of values to substitute (e.g., ["team1", "team2"])

    Returns:
        List of tuples: (resolved_url, {param_name: param_value})
    """
    resolved_endpoints = []
    for value in param_values:
        resolved_endpoint = endpoint_template.replace(f"{{{param_name}}}", str(value))
        resolved_endpoints.append((resolved_endpoint, {param_name: str(value)}))
    return resolved_endpoints


async def query_api_for_parameters(param_config: ApiPathParameter) -> List[str]:
    """Query an API to get values for a path parameter

    Args:
        param_config: Configuration for fetching parameter values

    Returns:
        List of parameter values extracted from API response
    """
    http_client = init_client()
    logger.info(f"Querying API for parameter values from {param_config.endpoint}")

    try:
        async for batch in http_client.fetch_paginated_data(
            endpoint=param_config.endpoint,
            method=param_config.method,
            query_params=param_config.query_params,
            headers=param_config.headers,
        ):
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


async def resolve_dynamic_endpoints(
    selector: HttpServerSelector, kind: str
) -> List[tuple[str, Dict[str, str]]]:
    """Resolve dynamic endpoints with path parameter values

    Args:
        selector: The resource selector configuration
        kind: The endpoint path (e.g., "/api/v1/users" or "/api/v1/teams/{team_id}")

    Returns:
        List of tuples: (resolved_url, {param_name: param_value})
        For static endpoints, returns [(kind, {})]
    """
    if not kind:
        logger.error("Kind (endpoint) is empty")
        return []

    # Get path_parameters from selector if they exist
    path_parameters = getattr(selector, "path_parameters", None) or {}

    # Find path parameters in endpoint template
    param_names = extract_path_parameters(kind)

    if not param_names:
        # No path parameters - return static endpoint with empty params
        return [(kind, {})]

    # Validate that all parameters are configured
    missing_params = validate_endpoint_parameters(param_names, path_parameters)
    if missing_params:
        logger.error(f"Missing configuration for path parameters: {missing_params}")
        return [(kind, {})]

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

    # Generate resolved endpoints with parameter values
    resolved_endpoints = generate_resolved_endpoints(kind, param_name, parameter_values)

    logger.info(
        f"Resolved {len(resolved_endpoints)} endpoints from parameter '{param_name}'"
    )
    return resolved_endpoints
