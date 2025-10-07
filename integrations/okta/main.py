from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from okta.clients.client_factory import OktaClientFactory
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

    client = OktaClientFactory.get_client()
    user_exporter = OktaUserExporter(client)

    config = cast(OktaUserConfig, event.resource_config)
    options: ListUserOptions = {
        "include_groups": config.selector.include_groups,
        "include_applications": config.selector.include_applications,
        "fields": config.selector.fields,
    }
    async for users in user_exporter.get_paginated_resources(options):
        yield users


@ocean.on_resync(ObjectKind.GROUP)
async def resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all groups from Okta."""
    logger.info(f"Starting resync for kind: {kind}")

    client = OktaClientFactory.get_client()
    group_exporter = OktaGroupExporter(client)

    async for groups in group_exporter.get_paginated_resources({}):
        yield groups
