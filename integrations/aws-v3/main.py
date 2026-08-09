from typing import cast

from aws.core.exporters.exporter_metadata import kind_to_export_metadata
from aws.utils import RegionHelper
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.helpers.types import ObjectKind
from aws.core.exporters.organizations.account.exporter import (
    OrganizationsAccountExporter,
)
from aws.core.exporters.organizations.account.models import PaginatedAccountRequest
from aws.core.helpers.utils import is_access_denied_exception
from aws.webhook.registry import register_cloudtrail_live_events

from loguru import logger
from resync import ResyncAWSService
from aws.auth.session_factory import (
    initialize_aws_account_sessions,
    clear_aws_account_sessions,
)

register_cloudtrail_live_events()


@ocean.on_resync_start()
async def initialize_aws_sessions() -> None:
    """Initialize AWS account sessions before resync."""
    await initialize_aws_account_sessions()


@ocean.on_resync_complete()
async def cleanup_aws_sessions() -> None:
    """Clear AWS sessions from memory after resync completes."""
    await clear_aws_account_sessions()


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
        region = await RegionHelper.get_custom_partition_region_or_none(session) or ""
        options = PaginatedAccountRequest(
            include=aws_resource_config.selector.include_actions,
            account_id=account["Id"],
            region=region,
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


@ocean.on_resync()
async def resync_standard_objects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind not in kind_to_export_metadata:
        return

    metadata = kind_to_export_metadata[ObjectKind(kind)]
    async for batch in ResyncAWSService(
        kind=kind,
        exporter_cls=metadata.exporter,
        request_cls=metadata.paginated_request_model,
        regional=metadata.regional,
    ):
        yield batch
