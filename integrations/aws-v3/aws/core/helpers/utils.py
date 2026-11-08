from typing import Any, Callable, Awaitable, TypeVar, cast
from aiobotocore.session import AioSession
from aws.auth.region_resolver import RegionResolver
from loguru import logger
import asyncio
from botocore.exceptions import ClientError

from aws.core.helpers.aws_errors import (
    is_access_denied_exception,
    is_cloud_control_type_unavailable_exception,
    is_recoverable_aws_exception,
    is_resource_not_found_exception,
    is_throttling_exception,
)

T = TypeVar("T")

__all__ = [
    "execute_concurrent_aws_operations",
    "get_allowed_regions",
    "is_access_denied_exception",
    "is_cloud_control_type_unavailable_exception",
    "is_recoverable_aws_exception",
    "is_resource_not_found_exception",
    "is_throttling_exception",
    "require_aws_resource",
]


def require_aws_resource(
    items: list[T] | None,
    *,
    error_code: str,
    message: str,
    operation_name: str,
) -> list[T]:
    """Raise a not-found ClientError when a describe call returns no resources.

    Live-event handlers rely on this to distinguish a deleted resource from a
    successful empty inspect result when the AWS API returns an empty list.
    """
    if items:
        return items
    raise ClientError(
        {"Error": {"Code": error_code, "Message": message}},
        operation_name,
    )


async def get_allowed_regions(session: AioSession, selector: Any) -> list[str]:
    resolver = RegionResolver(session, selector)
    return list(await resolver.get_allowed_regions())


async def execute_concurrent_aws_operations(
    input_items: list[Any],
    operation_func: Callable[[Any], Awaitable[Any]],
    get_resource_identifier: Callable[[Any], str],
    operation_name: str,
    concurrency_limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Generic concurrent AWS operation executor with concurrency control.

    Args:
        input_items: List of input items (repositories, queues, instances, etc.)
        operation_func: Async function that takes an input item and returns result
        get_resource_identifier: Function to extract resource ID from input item
        operation_name: Name for logging (e.g., "repository policy")
        concurrency_limit: Maximum number of concurrent operations (default: 20)

    Returns:
        One entry per input item, in the same order as ``input_items``. An empty
        dict is returned for any item whose ``operation_func`` raised a
        recoverable AWS exception, so callers can rely on positional alignment
        when merging results with other concurrent operations.
    """
    semaphore = asyncio.BoundedSemaphore(concurrency_limit)

    async def bounded_operation(item: Any) -> Any:
        async with semaphore:
            return await operation_func(item)

    operation_results = await asyncio.gather(
        *(bounded_operation(item) for item in input_items),
        return_exceptions=True,
    )

    results: list[dict[str, Any]] = []
    success_count = 0
    for idx, result in enumerate(operation_results):
        if isinstance(result, Exception):
            resource_id = get_resource_identifier(input_items[idx])
            if is_recoverable_aws_exception(result):
                logger.warning(
                    f"Skipping {operation_name} for '{resource_id}': {result}"
                )
                results.append({})
                continue
            else:
                logger.error(
                    f"Error fetching {operation_name} for '{resource_id}': {result}"
                )
                raise result
        results.append(cast(dict[str, Any], result))
        success_count += 1

    logger.info(f"Successfully fetched {operation_name} for {success_count} resources")
    return results
