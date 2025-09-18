from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from okta.clients.client_factory import create_okta_client
from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.exporters.group_exporter import OktaGroupExporter
from okta.core.options import ListUserOptions, ListGroupOptions
from integration import (
    OktaUserConfig,
    OktaGroupConfig,
)


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Okta integration (resync-only branch)."""
    logger.info("Starting Port Ocean Okta integration")


@ocean.on_resync("okta-user")
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all users from Okta."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_okta_client()
    exporter = OktaUserExporter(client)

    config = cast(OktaUserConfig, event.resource_config)
    options = ListUserOptions(
        include_groups=getattr(config.selector, "include_groups", False),
        include_applications=getattr(config.selector, "include_applications", False),
    )

    async for users in exporter.get_paginated_resources(options):
        yield users


@ocean.on_resync("okta-group")
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all groups from Okta."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_okta_client()
    exporter = OktaGroupExporter(client)

    config = cast(OktaGroupConfig, event.resource_config)
    options = ListGroupOptions(
        include_members=getattr(config.selector, "include_members", False),
    )

    async for groups in exporter.get_paginated_resources(options):
        yield groups


# Webhook registration is handled in the live-events branch
