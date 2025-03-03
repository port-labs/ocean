import enum


from port_ocean.context.ocean import ocean
from utils.overrides import AWSResourceConfig
from typing import (
    List,
    Literal,
    Protocol,
    Dict,
    Any,
    Optional,
    TYPE_CHECKING,
    AsyncGenerator,
)
import asyncio
from collections import deque
from loguru import logger

if TYPE_CHECKING:
    from aioboto3.client import AioBaseClient  # type: ignore


class CloudControlClientProtocol(Protocol):
    async def get_resource(
        self, *, TypeName: str, Identifier: str
    ) -> Dict[str, Any]: ...

    async def list_resources(
        self, *, TypeName: str, NextToken: str | None = None
    ) -> Dict[str, Any]: ...


class CloudControlThrottlingConfig(enum.Enum):
    MAX_RATE: int = 10
    TIME_PERIOD: float = 1  # in seconds
    SEMAPHORE: int = 10
    MAX_RETRY_ATTEMPTS: int = 100
    RETRY_MODE: Literal["legacy", "standard", "adaptive"] = "adaptive"


def get_semaphore() -> asyncio.BoundedSemaphore:
    max_concurrent_accounts: int = int(
        ocean.integration_config["maximum_concurrent_accounts"]
    )
    semaphore = asyncio.BoundedSemaphore(max_concurrent_accounts)
    return semaphore


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
    SQS_QUEUE = "AWS::SQS::Queue"


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


def is_resource_not_found_exception(e: Exception) -> bool:
    resource_not_found_error_codes = [
        "ResourceNotFoundException",
        "ResourceNotFound",
        "ResourceNotFoundFault",
    ]

    if hasattr(e, "response") and e.response is not None:
        error_code = e.response.get("Error", {}).get("Code")
        return error_code in resource_not_found_error_codes

    return False


def get_matching_kinds_and_blueprints_from_config(
    kind: str, region: str, resource_configs: List[AWSResourceConfig]
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    allowed_kinds: dict[str, list[str]] = {}
    disallowed_kinds: dict[str, list[str]] = {}
    for resource in resource_configs:
        blueprint = resource.port.entity.mappings.blueprint.strip('"')
        resource_selector = resource.selector
        if not resource_selector.is_region_allowed(region) and kind == resource.kind:
            if kind in disallowed_kinds:
                disallowed_kinds[kind].append(blueprint)
            else:
                disallowed_kinds[kind] = [blueprint]
        elif kind == resource.kind:
            if kind in allowed_kinds:
                allowed_kinds[kind].append(blueprint)
            else:
                allowed_kinds[kind] = [blueprint]

    return allowed_kinds, disallowed_kinds


class AsyncPaginator:

    _RESYNC_BATCH_SIZE = 100
    __slots__ = ("client", "method_name", "list_param")

    def __init__(self, client: "AioBaseClient", method_name: str, list_param: str):
        self.client = client
        self.method_name = method_name
        self.list_param = list_param

    async def paginate(self, **kwargs: Any) -> AsyncGenerator[List[Any], None]:
        """
        Asynchronously iterates over API pages.
        Each iteration yields the list of items extracted from the API page.
        """
        paginator = self.client.get_paginator(self.method_name)
        async for page in paginator.paginate(**kwargs):
            yield page.get(self.list_param, [])

    async def batch_paginate(
        self, batch_size: Optional[int] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Any], None]:
        """
        Aggregates items from all pages and yields them in batches of 'batch_size'.
        Items are buffered in a deque to avoid repeated list slicing.
        """
        batch_size = batch_size or self._RESYNC_BATCH_SIZE
        buffer: deque[Any] = deque()
        page = 1
        async for items in self.paginate(**kwargs):
            logger.debug(
                f"Fetched {len(items)} items from page {page} for resource with args: {kwargs}"
            )
            buffer.extend(items)
            while len(buffer) >= batch_size:
                batch = [buffer.popleft() for _ in range(batch_size)]
                logger.debug(
                    f"Yielding a batch of {len(batch)}/{len(items)} items from page {page} for resource with args: {kwargs}"
                )
                yield batch
            page += 1

        if buffer:
            final_batch = list(buffer)
            logger.debug(
                f"Yielding the final batch of {len(final_batch)} items from page {page}"
            )
            yield final_batch
