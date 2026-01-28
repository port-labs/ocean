"""
Endpoint Resolution Module

Handles dynamic endpoint resolution for path parameters.
"""

import re
from typing import AsyncGenerator, List, Dict, Any, Optional
from loguru import logger

from port_ocean.core.handlers.entity_processor.jq_entity_processor_sync import (
    JQEntityProcessorSync,
)
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
    return [
        (endpoint_template.replace(f"{{{param_name}}}", str(v)), {param_name: str(v)})
        for v in param_values
    ]


def _get_items_from_response(
    response_item: Dict[str, Any], data_path: Optional[str]
) -> List[Dict[str, Any]]:
    """Extract items from API response using JQ data_path

    Args:
        response_item: Single response item from API batch
        data_path: Optional JQ path to extract nested data

    Returns:
        List of items extracted from response
    """
    if not data_path:
        return [response_item]

    try:
        extracted = JQEntityProcessorSync._search(response_item, data_path)
        if extracted is None:
            return []
        return extracted if isinstance(extracted, list) else [extracted]
    except Exception as e:
        logger.error(f"Error extracting data with path '{data_path}': {e}")
        return []


def _get_filtered_value(
    item: Dict[str, Any],
    field: str,
    filter_expr: Optional[str],
) -> Optional[str]:
    """Extract field value from item, applying optional filter

    Args:
        item: Data item to extract value from
        field: JQ expression to extract the field value
        filter_expr: Optional JQ filter expression

    Returns:
        Extracted string value if valid and passes filter, None otherwise
    """
    try:
        value = JQEntityProcessorSync._search(item, field)
        if value is None:
            return None
        if filter_expr and JQEntityProcessorSync._search(item, filter_expr) is not True:
            return None
        return str(value)
    except Exception as e:
        logger.warning(f"Error extracting value from item: {e}")
        return None


async def query_api_for_parameters(
    param_config: ApiPathParameter,
) -> AsyncGenerator[List[str], None]:
    """Query an API to get values for a path parameter

    Args:
        param_config: Configuration for fetching parameter values

    Yields:
        Batches of parameter values extracted from API response
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
            values = [
                v
                for response_item in batch
                for item in _get_items_from_response(
                    response_item, param_config.data_path
                )
                if (
                    v := _get_filtered_value(
                        item, param_config.field, param_config.filter
                    )
                )
                is not None
            ]
            if values:
                yield values

    except Exception as e:
        logger.error(
            f"Error querying API for parameter values from {param_config.endpoint}: {e}"
        )


async def resolve_dynamic_endpoints(
    selector: HttpServerSelector, kind: str
) -> AsyncGenerator[List[tuple[str, Dict[str, str]]], None]:
    """Resolve dynamic endpoints with path parameter values

    Args:
        selector: The resource selector configuration
        kind: The endpoint path (e.g., "/api/v1/users" or "/api/v1/teams/{team_id}")

    Yields:
        Batches of tuples: (resolved_url, {param_name: param_value})
        For static endpoints, yields [(kind, {})]
    """
    if not kind:
        logger.error("Kind (endpoint) is empty")
        return

    # Get path_parameters from selector if they exist
    path_parameters = getattr(selector, "path_parameters", None) or {}

    # Find path parameters in endpoint template
    param_names = extract_path_parameters(kind)

    if not param_names:
        # No path parameters - yield static endpoint with empty params as single-item batch
        yield [(kind, {})]
        return

    # Validate that all parameters are configured
    missing_params = validate_endpoint_parameters(param_names, path_parameters)
    if missing_params:
        logger.error(f"Missing configuration for path parameters: {missing_params}")
        yield [(kind, {})]
        return

    # For now, handle single parameter (can extend for multiple later)
    if len(param_names) > 1:
        logger.warning(
            f"Multiple path parameters detected: {param_names}. "
            "Only the first parameter will be resolved."
        )

    param_name = param_names[0]
    param_config = path_parameters[param_name]

    # Track if any values were yielded
    has_values = False

    # Query API for parameter values and yield endpoint batches
    async for value_batch in query_api_for_parameters(param_config):
        has_values = True
        # Use existing helper to generate all endpoints for this batch
        endpoints = generate_resolved_endpoints(kind, param_name, value_batch)
        yield endpoints

    if not has_values:
        logger.error(f"No valid values found for path parameter '{param_name}'")
