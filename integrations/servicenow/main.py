from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import initialize_client
from webhook.initialize_client import initialize_webhook_client
from webhook.webhook_client import WEBHOOK_ENDPOINT
from webhook.processors.incident_processor import IncidentWebhookProcessor
from webhook.processors.service_catalog_processor import ServiceCatalogWebhookProcessor
from webhook.processors.user_group_processor import UserGroupWebhookProcessor
from webhook.processors.release_project_processor import (
    ReleaseProjectWebhookProcessor,
)
from webhook.processors.vulnerability_processor import (
    VulnerabilityWebhookProcessor,
)
from integration import ServiceNowResourceConfig


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Servicenow resource: {kind}")
    servicenow_client = initialize_client(
        servicenow_url=ocean.integration_config["servicenow_url"],
        client_id=ocean.integration_config.get("servicenow_client_id"),
        client_secret=ocean.integration_config.get("servicenow_client_secret"),
        username=ocean.integration_config.get("servicenow_username"),
        password=ocean.integration_config.get("servicenow_password"),
    )
    api_query_params = {}
    selector = cast(ServiceNowResourceConfig, event.resource_config).selector
    if selector.api_query_params:
        api_query_params = selector.api_query_params.generate_request_params()
    async for records in servicenow_client.get_paginated_resource(
        resource_kind=kind, api_query_params=api_query_params
    ):
        logger.info(f"Received {kind} batch with {len(records)} records")
        yield records


@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration and configure webhooks"""

    print("Starting Servicenow integration")
    servicenow_client = initialize_client(
        servicenow_url=ocean.integration_config["servicenow_url"],
        client_id=ocean.integration_config.get("servicenow_client_id"),
        client_secret=ocean.integration_config.get("servicenow_client_secret"),
        username=ocean.integration_config.get("servicenow_username"),
        password=ocean.integration_config.get("servicenow_password"),
    )
    await servicenow_client.sanity_check()

    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    enable_tables_live_events_webhooks = ocean.integration_config.get(
        "enable_tables_live_events_webhooks"
    )
    if not enable_tables_live_events_webhooks:
        logger.info("Skipping webhook creation as it's not enabled")
        return

    live_event_tables = ocean.integration_config.get("live_event_tables")
    if not live_event_tables:
        logger.info("Skipping webhook creation as no tables are specified")
        return

    webhook_client = initialize_webhook_client()
    tables = [table.strip() for table in live_event_tables]
    await webhook_client.create_webhook(base_url, tables)


ocean.add_webhook_processor(WEBHOOK_ENDPOINT, IncidentWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ServiceCatalogWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, UserGroupWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, ReleaseProjectWebhookProcessor)
ocean.add_webhook_processor(WEBHOOK_ENDPOINT, VulnerabilityWebhookProcessor)
