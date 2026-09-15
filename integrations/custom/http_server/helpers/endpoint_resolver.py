"""
Endpoint Resolution Module

Handles dynamic endpoint resolution for path parameters.
"""

import re
from itertools import product
from typing import AsyncGenerator, List, Dict, Any, Optional, Iterator, Tuple

from loguru import logger

from port_ocean.core.handlers.entity_processor.jq_entity_processor_sync import (
    JQEntityProcessorSync,
)
from http_server.overrides import HttpServerSelector, ApiPathParameter
from http_server.helpers.endpoint_cache import get_endpoint_cache

RESOLVED_REQUEST_BATCH_SIZE = 1000
MAX_DISCOVERED_QUERY_VALUES_PER_KEY = 5000


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
        (
            endpoint_template.replace(f"{{{param_name}}}", str(param_value)),
            {param_name: str(param_value)},
        )
        for param_value in param_values
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
    except Exception as error:
        logger.error(f"Error extracting data with path '{data_path}': {error}")
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
    except Exception as error:
        logger.warning(f"Error extracting value from item: {error}")
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
    from initialize_client import init_client

    http_client = init_client()
    logger.info(f"Querying API for parameter values from {param_config.endpoint}")

    cache = get_endpoint_cache()

    def _fetch() -> AsyncGenerator[List[Dict[str, Any]], None]:
        return http_client.fetch_paginated_data(
            endpoint=param_config.endpoint,
            method=param_config.method,
            query_params=param_config.query_params,
            headers=param_config.headers,
        )

    raw_source: AsyncGenerator[List[Dict[str, Any]], None]
    if cache is not None:
        raw_source = cache.get_or_fetch(
            endpoint=param_config.endpoint,
            method=param_config.method,
            query_params=param_config.query_params,
            headers=param_config.headers,
            body=None,
            fetch_fn=_fetch,
        )
    else:
        raw_source = _fetch()

    try:
        async for batch in raw_source:
            values = [
                filtered_value
                for response_item in batch
                for item in _get_items_from_response(
                    response_item, param_config.data_path
                )
                if (
                    filtered_value := _get_filtered_value(
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
) -> AsyncGenerator[List[tuple[str, Dict[str, str], Dict[str, Any]]], None]:
    """Resolve dynamic endpoints with path parameter values

    Args:
        selector: The resource selector configuration
        kind: The endpoint path (e.g., "/api/v1/users" or "/api/v1/teams/{team_id}")

    Yields:
        Batches of tuples: (resolved_url, path_params, dynamic_query_params)
        For static endpoints, yields [(kind, {}, {})]
    """
    if not kind:
        logger.error("Kind (endpoint) is empty")
        return

    # Get path_parameters from selector if they exist
    path_parameters = getattr(selector, "path_parameters", None) or {}
    dynamic_query_params = getattr(selector, "dynamic_query_params", None) or {}

    async def _resolve_dynamic_query_values() -> (
        Optional[Tuple[List[str], List[List[str]]]]
    ):
        if not dynamic_query_params:
            return None

        values_by_key: Dict[str, List[str]] = {}

        for query_key, query_param_config in dynamic_query_params.items():
            values: List[str] = []
            async for value_batch in query_api_for_parameters(query_param_config):
                remaining = MAX_DISCOVERED_QUERY_VALUES_PER_KEY - len(values)
                if remaining <= 0:
                    logger.warning(
                        f"Reached max discovered values ({MAX_DISCOVERED_QUERY_VALUES_PER_KEY}) "
                        f"for query parameter '{query_key}'. Truncating additional values."
                    )
                    break

                if len(value_batch) > remaining:
                    logger.warning(
                        f"Truncating discovered values for query parameter '{query_key}' "
                        f"to {MAX_DISCOVERED_QUERY_VALUES_PER_KEY} to limit memory growth."
                    )
                    values.extend(value_batch[:remaining])
                    break

                values.extend(value_batch)

            unique_values = list(dict.fromkeys(values))
            if not unique_values:
                logger.error(
                    f"No valid values found for query parameter '{query_key}' from "
                    f"{query_param_config.endpoint}"
                )
                return None

            values_by_key[query_key] = unique_values

        query_keys = list(values_by_key.keys())
        query_values = [values_by_key[key] for key in query_keys]
        return query_keys, query_values

    def _iter_dynamic_query_combinations(
        query_keys: List[str], query_values: List[List[str]]
    ) -> Iterator[Dict[str, Any]]:
        for query_tuple in product(*query_values):
            yield dict(zip(query_keys, query_tuple))

    def _iter_resolved_request_batches(
        endpoints: List[tuple[str, Dict[str, str]]],
        query_keys: Optional[List[str]],
        query_values: Optional[List[List[str]]],
    ) -> Iterator[List[tuple[str, Dict[str, str], Dict[str, Any]]]]:
        """Yield resolved requests in bounded chunks to control memory growth."""
        batch: List[tuple[str, Dict[str, str], Dict[str, Any]]] = []

        if query_keys is None or query_values is None:
            for endpoint, path_params in endpoints:
                batch.append((endpoint, path_params, {}))
                if len(batch) >= RESOLVED_REQUEST_BATCH_SIZE:
                    yield batch
                    batch = []
            if batch:
                yield batch
            return

        for endpoint, path_params in endpoints:
            for dynamic_query in _iter_dynamic_query_combinations(
                query_keys, query_values
            ):
                batch.append((endpoint, path_params, dynamic_query))
                if len(batch) >= RESOLVED_REQUEST_BATCH_SIZE:
                    yield batch
                    batch = []

        if batch:
            yield batch

    query_value_matrix = await _resolve_dynamic_query_values()
    if dynamic_query_params and query_value_matrix is None:
        return

    # Find path parameters in endpoint template
    param_names = extract_path_parameters(kind)

    if not param_names:
        # No path parameters - yield static endpoint with empty params as single-item batch
        if query_value_matrix is None:
            yield [(kind, {}, {})]
            return

        query_keys, query_values = query_value_matrix
        estimated_combinations = 1
        for values in query_values:
            estimated_combinations *= len(values)
        if estimated_combinations > RESOLVED_REQUEST_BATCH_SIZE:
            logger.info(
                f"Large dynamic query expansion detected for '{kind}': "
                f"{estimated_combinations} request variants; streaming in "
                f"chunks of {RESOLVED_REQUEST_BATCH_SIZE}"
            )
        for resolved_batch in _iter_resolved_request_batches(
            [(kind, {})], query_keys, query_values
        ):
            yield resolved_batch
        return

    # Validate that all parameters are configured
    missing_params = validate_endpoint_parameters(param_names, path_parameters)
    if missing_params:
        logger.error(f"Missing configuration for path parameters: {missing_params}")
        if query_value_matrix is not None:
            logger.warning(
                "Skipping dynamic query parameter expansion because path parameters "
                "are unresolved in endpoint template"
            )
        # Avoid fan-out on unresolved endpoint templates.
        yield [(kind, {}, {})]
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
        if query_value_matrix is None:
            for resolved_batch in _iter_resolved_request_batches(endpoints, None, None):
                yield resolved_batch
            continue

        query_keys, query_values = query_value_matrix
        for resolved_batch in _iter_resolved_request_batches(
            endpoints, query_keys, query_values
        ):
            yield resolved_batch

    if not has_values:
        logger.error(f"No valid values found for path parameter '{param_name}'")
