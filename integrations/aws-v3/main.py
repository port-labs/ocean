from typing import TYPE_CHECKING, List, Callable, Any, cast
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.exporters.s3 import S3BucketExporter
from aws.core.helpers.utils import get_allowed_regions
from aws.core.helpers.types import ObjectKind
from aws.core.exporters.s3.bucket.models import PaginatedBucketRequest
from aws.core.exporters.ec2.instance import PaginatedEC2InstanceRequest
from aws.core.exporters.ec2.instance import EC2InstanceExporter
from loguru import logger
import asyncio
from functools import partial
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)


if TYPE_CHECKING:
    from aws.core.interfaces.exporter import IResourceExporter


async def _handle_global_resource_resync(
    regions: List[str],
    options_factory: Callable[[str], Any],
    exporter: "IResourceExporter",
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for region in regions:
        options = options_factory(region)
        async for batch in exporter.get_paginated_resources(options):
            yield batch
        return


async def _handle_regional_resource_resync(
    exporter: "IResourceExporter",
    options_factory: Callable[[str], Any],
    kind: str,
    regions: List[str],
    account_id: str,
    max_concurrent: int = 10,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(
        f"Processing {kind} across {len(regions)} regions for account {account_id}"
    )
    semaphore = asyncio.Semaphore(max_concurrent)

    tasks = [
        semaphore_async_iterator(
            semaphore,
            partial(exporter.get_paginated_resources, options_factory(region)),
        )
        for region in regions
    ]

    async for batch in stream_async_iterators_tasks(*tasks):
        if batch:
            yield batch


@ocean.on_resync(ObjectKind.S3_BUCKET)
async def resync_s3_bucket(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    def options_factory(region: str) -> PaginatedBucketRequest:
        return PaginatedBucketRequest(
            region=region,
            include=aws_resource_config.selector.include_actions,
            account_id=account["Id"],
        )

    async for account, session in get_all_account_sessions():
        logger.info(f"Resyncing S3 buckets for account {account['Id']}")
        regions = await get_allowed_regions(session, aws_resource_config.selector)
        logger.info(
            f"Found {len(regions)} allowed regions: {regions} for account {account['Id']}"
        )
        exporter = S3BucketExporter(session)

        async for batch in _handle_global_resource_resync(
            regions, options_factory, exporter
        ):
            logger.info(f"Found {len(batch)} S3 buckets for account {account['Id']}")
            yield batch


@ocean.on_resync(ObjectKind.EC2_INSTANCE)
async def resync_ec2_instance(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    def options_factory(region: str) -> PaginatedEC2InstanceRequest:
        return PaginatedEC2InstanceRequest(
            region=region,
            include=aws_resource_config.selector.include_actions,
            account_id=account["Id"],
        )

    async for account, session in get_all_account_sessions():
        logger.info(f"Resyncing EC2 instances for account {account['Id']}")
        regions = await get_allowed_regions(session, aws_resource_config.selector)
        logger.info(f"Found {len(regions)} allowed regions for account {account['Id']}")
        exporter = EC2InstanceExporter(session)

        async for batch in _handle_regional_resource_resync(
            exporter, options_factory, kind, regions, account["Id"]
        ):
            yield batch


@ocean.on_resync(ObjectKind.ECS_CLUSTER)
async def resync_ecs_cluster(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    def options_factory(region: str) -> PaginatedClusterRequest:
        return PaginatedClusterRequest(
            region=region,
            include=aws_resource_config.selector.include_actions,
            account_id=account["Id"],
        )

    async for account, session in get_all_account_sessions():
        logger.info(f"Resyncing ECS clusters for account {account['Id']}")
        regions = await get_allowed_regions(session, aws_resource_config.selector)
        logger.info(
            f"Found {len(regions)} allowed regions: {regions} for account {account['Id']}"
        )
        exporter = EcsClusterExporter(session)

        async for batch in _handle_regional_resource_resync(
            exporter, options_factory, kind, regions, account["Id"]
        ):
            logger.info(f"Found {len(batch)} ECS clusters for account {account['Id']}")
            yield batch
