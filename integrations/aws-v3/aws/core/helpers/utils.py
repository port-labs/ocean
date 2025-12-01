from typing import Any, Callable, Awaitable
from aiobotocore.session import AioSession
from aws.auth.region_resolver import RegionResolver
from loguru import logger
import asyncio


def is_access_denied_exception(e: Exception) -> bool:
    access_denied_error_codes = [
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    ]
    response = getattr(e, "response", None)
    if isinstance(response, dict):
        error_code = response.get("Error", {}).get("Code")
        return error_code in access_denied_error_codes
    return False


def is_resource_not_found_exception(e: Exception) -> bool:
    resource_not_found_error_codes = [
        "ResourceNotFoundException",
        "ResourceNotFound",
        "ResourceNotFoundFault",
        "RepositoryPolicyNotFoundException",
        "LifecyclePolicyNotFoundException",
    ]
    response = getattr(e, "response", None)
    if isinstance(response, dict):
        error_code = response.get("Error", {}).get("Code")
        return error_code in resource_not_found_error_codes
    return False


def is_recoverable_aws_exception(exception: Exception) -> bool:
    """
    Check if an AWS exception is recoverable and the action can continue.
    Recoverable exceptions (ResourceNotFound, AccessDenied) allow processing to continue.
    Non-recoverable exceptions should be re-raised to break the action.

    Args:
        exception: The exception to check

    Returns:
        True if exception is recoverable and processing can continue, False if it should be re-raised
    """
    return is_resource_not_found_exception(exception) or is_access_denied_exception(
        exception
    )


async def get_allowed_regions(session: AioSession, selector: Any) -> list[str]:
    resolver = RegionResolver(session, selector)
    return list(await resolver.get_allowed_regions())


async def execute_concurrent_aws_operations(
    input_items: list[Any],
    operation_func: Callable[[Any], Awaitable[Any]],
    get_resource_identifier: Callable[[Any], str],
    operation_name: str,
) -> list[dict[str, Any]]:
    """
    Generic concurrent AWS operation executor.

    Args:
        input_items: List of input items (repositories, queues, instances, etc.)
        operation_func: Async function that takes an input item and returns result
        get_resource_identifier: Function to extract resource ID from input item
        operation_name: Name for logging (e.g., "repository policy")

    Returns:
        List of successful operation results
    """
    operation_results = await asyncio.gather(
        *(operation_func(item) for item in input_items),
        return_exceptions=True,
    )

    results: list[dict[str, Any]] = []
    for idx, result in enumerate(operation_results):
        if isinstance(result, Exception):
            resource_id = get_resource_identifier(input_items[idx])
            if is_recoverable_aws_exception(result):
                logger.warning(
                    f"Skipping {operation_name} for '{resource_id}': {result}"
                )
                continue
            else:
                logger.error(
                    f"Error fetching {operation_name} for '{resource_id}': {result}"
                )
                raise result
        results.append(result)

    logger.info(f"Successfully fetched {operation_name} for {len(results)} resources")
    return results
