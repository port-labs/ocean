from typing import TYPE_CHECKING, List, Callable, Any, cast
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.exporters.s3 import S3BucketExporter
from aws.core.exporters.ecs import ECSClusterExporter
from aws.core.helpers.utils import get_allowed_regions, is_access_denied_exception
from aws.core.helpers.types import ObjectKind
from aws.core.exporters.s3.bucket.models import PaginatedBucketRequest
from loguru import logger

if TYPE_CHECKING:
    from aws.core.interfaces.exporter import IResourceExporter


async def _handle_global_resource_resync(
    kind: str,
    regions: List[str],
    options_factory: Callable[[str], Any],
    exporter: "IResourceExporter",
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for region in regions:
        try:
            options = options_factory(region)
            async for batch in exporter.get_paginated_resources(options):
                yield batch
            return
        except Exception as e:
            if is_access_denied_exception(e):
                logger.warning(
                    f"Access denied in region '{region}' for kind '{kind}', skipping."
                )
                continue
            else:
                raise e


async def _handle_regional_resource_resync(
    kind: str,
    regions: List[str],
    options_factory: Callable[[str], Any],
    exporter: "IResourceExporter",
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for region in regions:
        try:
            options = options_factory(region)
            async for batch in exporter.get_paginated_resources(options):
                yield batch
        except Exception as e:
            if is_access_denied_exception(e):
                logger.warning(
                    f"Access denied in region '{region}' for kind '{kind}', skipping."
                )
                continue
            else:
                raise e


@ocean.on_resync(ObjectKind.S3_BUCKET)
async def resync_s3_bucket(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    def options_factory(region: str) -> PaginatedBucketRequest:
        return PaginatedBucketRequest(
            region=region, include=aws_resource_config.selector.include_actions
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


@ocean.on_resync(ObjectKind.ECS_CLUSTER)
async def resync_ecs_cluster(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    def options_factory(region: str) -> PaginatedECSClusterExporterOptions:
        return PaginatedECSClusterExporterOptions(
            region=region, include=aws_resource_config.selector.include_actions
        )

    async for account, session in get_all_account_sessions():
        logger.info(f"Resyncing ECS clusters for account {account['Id']}")
        regions = await get_allowed_regions(session, aws_resource_config.selector)
        logger.info(
            f"Found {len(regions)} allowed regions: {regions} for account {account['Id']}"
        )
        exporter = ECSClusterExporter(session)

        async for batch in _handle_regional_resource_resync(
            kind, regions, options_factory, exporter
        ):
            logger.info(f"Found {len(batch)} ECS clusters for account {account['Id']}")
            yield batch
