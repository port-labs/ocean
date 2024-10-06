import enum
from typing import Any, AsyncIterator, Callable

from port_ocean.context.event import event
import asyncio


MAX_CONCURRENT_TASKS = 50
semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_TASKS)


class CustomProperties(enum.StrEnum):
    ACCOUNT_ID = "__AccountId"
    KIND = "__Kind"
    REGION = "__Region"


class ResourceKindsWithSpecialHandling(enum.StrEnum):
    ACCOUNT = "AWS::Organizations::Account"
    AMI_IMAGE = "AWS::ImageBuilder::Image"
    ACM_CERTIFICATE = "AWS::ACM::Certificate"
    CLOUDFORMATION_STACK = "AWS::CloudFormation::Stack"
    ELASTICACHE_CLUSTER = "AWS::ElastiCache::Cluster"
    ELBV2_LOAD_BALANCER = "AWS::ELBV2::LoadBalancer"


def is_access_denied_exception(e: Exception) -> bool:
    access_denied_error_codes = [
        "AccessDenied",
        "AccessDeniedException",
        "UnauthorizedOperation",
    ]

    if hasattr(e, "response") and e.response is not None:
        error_code = e.response.get("Error", {}).get("Code")
        return error_code in access_denied_error_codes

    return False


def is_server_error(e: Exception) -> bool:
    if hasattr(e, "response"):
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        return status >= 500

    return False


def get_matching_kinds_and_blueprints_from_config(
    kind: str,
) -> dict[str, list[str]]:
    kinds: dict[str, list[str]] = {}
    resources = event.port_app_config.resources

    for resource in resources:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        if resource.kind in kinds:
            kinds[resource.kind].append(blueprint)
        elif kind == resource.kind:
            kinds[resource.kind] = [blueprint]

    return kinds


async def semaphore_async_iterator(
    semaphore: asyncio.Semaphore, function: Callable[[], AsyncIterator[Any]]
) -> AsyncIterator[Any]:
    """
    Executes an asynchronous iterator function under a semaphore to limit concurrency.

    This function ensures that the provided asynchronous iterator function is executed
    while respecting the concurrency limit imposed by the semaphore. It acquires the
    semaphore before executing the function and releases it after the function completes,
    thus controlling the number of concurrent executions.

    Parameters:
        semaphore (asyncio.Semaphore | asyncio.BoundedSemaphore): The semaphore used to limit concurrency.
        function (Callable[[], AsyncIterator[Any]]): A nullary asynchronous function, - apply arguments with `functools.partial` or an anonymous function (lambda)
            that returns an asynchronous iterator. This function is executed under the semaphore.

    Yields:
        Any: The items yielded by the asynchronous iterator function.

    Usage:
        ```python
        import asyncio

        async def async_iterator_function(param1, param2):
            # Your async code here
            yield ...

        async def async_generator_function():
            # Your async code to retrieve items
            param1 = "your_param1"
            yield param1

        async def main():
            semaphore = asyncio.BoundedSemaphore(50)
            param2 = "your_param2"

            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    lambda: async_iterator_function(param1, param2) # functools.partial(async_iterator_function, param1, param2)
                )
                async for param1 in async_generator_function()
            ]

            async for batch in stream_async_iterators_tasks(*tasks):
                # Process each batch
                pass

        asyncio.run(main())
        ```
    """
    async with semaphore:
        async for result in function():
            yield result
