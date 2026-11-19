from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from confluence.clients.client_factory import ClientFactory
from confluence.core.exporters.page_exporter import PageExporter
from confluence.core.exporters.space_exporter import SpaceExporter
from confluence.core.exporters.user_exporter import UserExporter
from confluence.core.options import (
    PageExportOptions,
    SpaceExportOptions,
    UserExportOptions,
)
from confluence.helpers.utils import ObjectKind
from integration import (
    ConfluencePageResourceConfig,
    ConfluenceSpaceResourceConfig,
    ConfluenceUserResourceConfig,
)


@ocean.on_start()
async def on_start() -> None:
    ClientFactory.get_client()
    logger.info("Confluence integration started")


@ocean.on_resync(ObjectKind.SPACE)
async def on_resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Confluence spaces."""
    selector = cast(ConfluenceSpaceResourceConfig, event.resource_config).selector
    exporter = SpaceExporter(ClientFactory.get_client())
    async for batch in exporter.get_paginated_resources(
        SpaceExportOptions(
            space_type=selector.space_type,
            status=selector.status,
            labels=selector.labels,
        )
    ):
        yield batch


@ocean.on_resync(ObjectKind.PAGE)
async def on_resync_pages(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync pages, including the space they belong to."""
    selector = cast(ConfluencePageResourceConfig, event.resource_config).selector
    exporter = PageExporter(ClientFactory.get_client())
    async for batch in exporter.get_paginated_resources(
        PageExportOptions(
            include_archived=selector.include_archived,
            include_body=selector.include_body,
            space_ids=selector.space_ids,
        )
    ):
        yield batch


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Confluence users."""
    selector = cast(ConfluenceUserResourceConfig, event.resource_config).selector
    exporter = UserExporter(ClientFactory.get_client())
    async for batch in exporter.get_paginated_resources(
        UserExportOptions(site_permission_type=selector.site_permission_type)
    ):
        yield batch
