from typing import cast, List

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from initialize_client import initialize_client
from webhook_processors.initialize_client import initialize_webhook_client
from integration import ServiceNowResourceConfig


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Servicenow resource: {kind}")
    servicenow_client = initialize_client()
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
    print("Starting Servicenow integration")
    servicenow_client = initialize_client()
    await servicenow_client.sanity_check()


@ocean.on_resync_start()
async def configure_webhooks() -> None:
    """Configure webhooks for the integration"""

    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    kinds: List[str] = [
        resource.kind for index, resource in enumerate(event.port_app_config.resources)
    ]
    webhook_client = initialize_webhook_client()
    await webhook_client.create_webhook(base_url, kinds)
