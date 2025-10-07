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
from okta.webhook_processors.user_webhook_processor import (
    OktaUserWebhookProcessor,
)
from okta.webhook_processors.group_webhook_processor import (
    OktaGroupWebhookProcessor,
)
from okta.webhook_processors.webhook_client import OktaWebhookClient


@ocean.on_start()
async def on_start() -> None:
    """Initialize the Okta integration"""
    logger.info("Starting Port Ocean Okta integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    # Create/ensure Okta Event Hook exists
    client = OktaClientFactory.get_client()
    webhook_client = OktaWebhookClient(
        okta_domain=client.okta_domain,
        api_token=client.api_token,
        max_retries=client.max_retries,
    )
    await webhook_client.ensure_event_hook(base_url)


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


# Webhook processors registration
ocean.add_webhook_processor("/webhook", OktaUserWebhookProcessor)
ocean.add_webhook_processor("/webhook", OktaGroupWebhookProcessor)
