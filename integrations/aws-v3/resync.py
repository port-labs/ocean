import asyncio
from functools import partial
from typing import Any, Callable, List, Type, AsyncIterator, cast, TYPE_CHECKING

from loguru import logger
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from integration import AWSResourceConfig
from aws.auth.session_factory import get_all_account_sessions
from aws.core.helpers.utils import get_allowed_regions, is_access_denied_exception
from aws.core.modeling.resource_models import ResourceRequestModel
from aws.auth.session_factory import AccountInfo
from aiobotocore.session import AioSession


if TYPE_CHECKING:
    from aws.core.interfaces.exporter import IResourceExporter

_MAX_CONCURRENT_REGIONS = 10


async def safe_region_iterator(
    region: str, kind: str, ait: AsyncIterator[Any]
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    try:
        async for item in ait:
            yield item
    except Exception as e:
        if is_access_denied_exception(e):
            logger.error(
                f"Region {region} failed during resync of {kind}: {e}, skipping ..."
            )
            return


async def handle_global_resource_resync(
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
            return  # global resources → only need one valid region
        except Exception as e:
            if is_access_denied_exception(e):
                logger.debug(
                    f"Global resource fetch failed in region {region} for {kind}: {e}, skipping ..."
                )
                continue
    logger.error(
        f"All candidate regions [{regions}] failed for global resource resync of {kind}"
    )


async def handle_regional_resource_resync(
    exporter: "IResourceExporter",
    options_factory: Callable[[str], Any],
    kind: str,
    regions: List[str],
    account_id: str,
    max_concurrent: int = _MAX_CONCURRENT_REGIONS,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(
        f"Processing {kind} across {len(regions)} regions for account {account_id}"
    )
    semaphore = asyncio.Semaphore(max_concurrent)

    tasks = [
        safe_region_iterator(
            region,
            kind,
            semaphore_async_iterator(
                semaphore,
                partial(exporter.get_paginated_resources, options_factory(region)),
            ),
        )
        for region in regions
    ]

    async for batch in stream_async_iterators_tasks(*tasks):
        if batch:
            yield batch


async def _resync_account(
    kind: str,
    exporter_cls: Type["IResourceExporter"],
    request_cls: Type[ResourceRequestModel],
    regional: bool,
    account: AccountInfo,
    session: AioSession,
    actions: List[str],
    regions: List[str],
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(
        f"Resyncing {kind} for account {account['Id']} across {len(regions)} regions"
    )

    exporter = exporter_cls(session)

    def options_factory(region: str) -> Any:
        return request_cls(
            region=region,
            include=actions,
            account_id=account["Id"],
        )

    if regional:
        async for batch in handle_regional_resource_resync(
            exporter, options_factory, kind, regions, account["Id"]
        ):
            yield batch
    else:
        async for batch in handle_global_resource_resync(
            kind, regions, options_factory, exporter
        ):
            yield batch


async def resync_resource(
    kind: str,
    exporter_cls: Type["IResourceExporter"],
    request_cls: Type[ResourceRequestModel],
    regional: bool,
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync resources across multiple accounts concurrently, with
    optional concurrency limit per account.
    """
    aws_resource_config = cast(AWSResourceConfig, event.resource_config)
    include_actions = aws_resource_config.selector.include_actions
    semaphore = asyncio.Semaphore(aws_resource_config.selector.max_concurrent_accounts)

    async def account_iterator() -> AsyncIterator[ASYNC_GENERATOR_RESYNC_TYPE]:
        async for account, session in get_all_account_sessions():
            regions = await get_allowed_regions(session, aws_resource_config.selector)
            yield safe_region_iterator(
                account["Id"],
                kind,
                semaphore_async_iterator(
                    semaphore,
                    partial(
                        _resync_account,
                        kind,
                        exporter_cls,
                        request_cls,
                        regional,
                        account,
                        session,
                        include_actions,
                        regions,
                    ),
                ),
            )

    tasks = [ait async for ait in account_iterator()]

    async for batch in stream_async_iterators_tasks(*tasks):
        if batch:
            yield batch
