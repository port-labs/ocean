from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from okta.clients.client_factory import create_okta_client
from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.exporters.group_exporter import OktaGroupExporter
from okta.core.options import ListUserOptions, ListGroupOptions
from okta.webhook_processors.user_webhook_processor import UserWebhookProcessor
from okta.webhook_processors.group_webhook_processor import GroupWebhookProcessor
from okta.webhook_processors.webhook_client import OktaWebhookClient
from integration import (
    OktaUserConfig,
    OktaGroupConfig,
)


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Okta integration."""
    logger.info("Starting Port Ocean Okta integration")
    
    # Create event hooks in Okta if they don't exist
    try:
        webhook_client = OktaWebhookClient()
        app_host = ocean.integration_config.get("app_host", "http://localhost:8000")
        await webhook_client.create_webhook_if_not_exists(app_host)
        logger.info("Okta event hooks setup completed")
    except Exception as e:
        logger.error(f"Failed to setup Okta event hooks: {e}")


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




# Register webhook processors for live events
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)
ocean.add_webhook_processor("/webhook", GroupWebhookProcessor)



