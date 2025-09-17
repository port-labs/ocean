from typing import cast
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.exporters.s3 import S3BucketExporter
from aws.core.helpers.types import ObjectKind
from aws.core.exporters.s3.bucket.models import PaginatedBucketRequest
from aws.core.exporters.ec2.instance import PaginatedEC2InstanceRequest
from aws.core.exporters.ec2.instance import EC2InstanceExporter
from aws.core.exporters.ecs.cluster.exporter import EcsClusterExporter
from aws.core.exporters.ecs.cluster.models import PaginatedClusterRequest
from aws.core.exporters.organizations.account.exporter import (
    OrganizationsAccountExporter,
)
from aws.core.exporters.organizations.account.models import PaginatedAccountRequest
from aws.core.helpers.utils import is_access_denied_exception

from loguru import logger
from resync import (
    resync_resource,
)


@ocean.on_resync(ObjectKind.S3_BUCKET)
async def resync_s3_bucket(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync_resource(
        kind, S3BucketExporter, PaginatedBucketRequest, regional=False
    ):
        yield batch


@ocean.on_resync(ObjectKind.EC2_INSTANCE)
async def resync_ec2_instance(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync_resource(
        kind, EC2InstanceExporter, PaginatedEC2InstanceRequest, regional=True
    ):
        yield batch


@ocean.on_resync(ObjectKind.ECS_CLUSTER)
async def resync_ecs_cluster(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for batch in resync_resource(
        kind, EcsClusterExporter, PaginatedClusterRequest, regional=True
    ):
        yield batch


@ocean.on_resync(ObjectKind.AccountInfo)
async def resync_single_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    batch = []
    BATCH_SIZE = 100

    async for account, _ in get_all_account_sessions():
        logger.info(f"Received single account for account {account['Id']}")
        batch.append({"Type": kind, "Properties": dict(account)})

        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []

    if batch:
        yield batch


@ocean.on_resync(ObjectKind.ORGANIZATIONS_ACCOUNT)
async def resync_organizations_account(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    aws_resource_config = cast(AWSResourceConfig, event.resource_config)

    async for account, session in get_all_account_sessions():

        logger.info(
            f"Attempting to fetch organizations accounts from account {account['Id']}"
        )

        exporter = OrganizationsAccountExporter(session)
        options = PaginatedAccountRequest(
            include=aws_resource_config.selector.include_actions,
            account_id=account["Id"],
            region="",
        )

        try:
            async for batch in exporter.get_paginated_resources(options):
                logger.info(
                    f"Found {len(batch)} organizations accounts under {account['Id']}"
                )
                yield batch

        except Exception as e:
            if is_access_denied_exception(e):
                logger.debug(
                    f"Access denied to list organizations accounts under {account['Id']}, skipping ..."
                )
                continue
            else:
                logger.error(f"Error resyncing Organizations accounts: {e}")
            continue
        # Only need one valid management/delegated account
        break
