from typing import List, Callable, Any
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.exporters.s3.exporter import S3BucketExporter
from aws.core.utils import get_allowed_regions, is_access_denied_exception
from aws.core.helpers.kinds import ObjectKind
from aws.core.interfaces.exporter import IResourceExporter
from aws.core.options import PaginatedS3BucketExporterOptions
from loguru import logger


async def _handle_global_resource_resync(
    kind: str,
    regions: List[str],
    options_factory: Callable[[str], Any],
    exporter: IResourceExporter
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for region in regions:
        try:
            options = options_factory(region)
            async for batch in exporter.get_paginated_resources(options):
                yield batch
            return
        except Exception as e:
            if is_access_denied_exception(e):
                logger.warning(f"Access denied in region '{region}' for kind '{kind}', skipping.")
                continue
            else:
                raise e


@ocean.on_resync(ObjectKind.S3_BUCKET)
async def resync_s3_bucket(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = event.resource_config
    assert isinstance(aws_resource_config, AWSResourceConfig), "Invalid resource config type."

    def options_factory(region: str) -> PaginatedS3BucketExporterOptions:
        return PaginatedS3BucketExporterOptions(region=region)

    async for account, session in get_all_account_sessions():
        regions = await get_allowed_regions(session, aws_resource_config.selector)
        exporter = S3BucketExporter(session)

        async for batch in _handle_global_resource_resync(kind, regions, options_factory, exporter):
            yield batch
