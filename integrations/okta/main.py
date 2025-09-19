from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from okta.clients.client_factory import create_okta_client
from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.exporters.group_exporter import OktaGroupExporter
from okta.core.options import ListUserOptions
from integration import (
    OktaUserConfig,
)
from okta.utils import ObjectKind


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Okta integration"""
    logger.info("Starting Port Ocean Okta integration")


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all users from Okta."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_okta_client()
    exporter = OktaUserExporter(client)

    config = cast(OktaUserConfig, event.resource_config)
    options = ListUserOptions(
        include_groups=getattr(config.selector, "include_groups", False),
        include_applications=getattr(config.selector, "include_applications", False),
        fields=getattr(config.selector, "fields", None),
    )
    async for users in exporter.get_paginated_resources(options):
        yield users


@ocean.on_resync(ObjectKind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all groups from Okta."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_okta_client()
    exporter = OktaGroupExporter(client)

    async for groups in exporter.get_paginated_resources(object()):
        yield groups
