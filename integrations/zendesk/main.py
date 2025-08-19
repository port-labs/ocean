import typing
from typing import cast

from loguru import logger
from initialize_client import create_zendesk_client
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from zendesk.overrides import (
    ZendeskTicketResourceConfig,
    ZendeskUserResourceConfig,
    ZendeskOrganizationResourceConfig,
    ZendeskGroupResourceConfig,
    ZendeskBrandResourceConfig,
)
from webhook_processors.ticket_webhook_processor import TicketWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor
from webhook_processors.organization_webhook_processor import OrganizationWebhookProcessor


@ocean.on_resync(Kinds.TICKET)
async def on_resync_tickets(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync tickets from Zendesk."""
    client = create_zendesk_client()
    
    params = {}
    config = typing.cast(ZendeskTicketResourceConfig, event.resource_config)
    
    # Apply filters based on selector configuration
    if config.selector.status:
        params["status"] = config.selector.status
        logger.info(f"Filtering tickets by status: {config.selector.status}")
        
    if config.selector.priority:
        params["priority"] = config.selector.priority
        logger.info(f"Filtering tickets by priority: {config.selector.priority}")
        
    if config.selector.assignee_id:
        params["assignee_id"] = config.selector.assignee_id
        logger.info(f"Filtering tickets by assignee ID: {config.selector.assignee_id}")
        
    if config.selector.organization_id:
        params["organization_id"] = config.selector.organization_id
        logger.info(f"Filtering tickets by organization ID: {config.selector.organization_id}")

    async for tickets in client.get_tickets(params):
        logger.info(f"Received ticket batch with {len(tickets)} tickets")
        yield tickets


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync users from Zendesk."""
    client = create_zendesk_client()
    
    params = {}
    config = typing.cast(ZendeskUserResourceConfig, event.resource_config)
    
    # Apply filters based on selector configuration
    if config.selector.role:
        params["role"] = config.selector.role
        logger.info(f"Filtering users by role: {config.selector.role}")
        
    if config.selector.organization_id:
        params["organization_id"] = config.selector.organization_id
        logger.info(f"Filtering users by organization ID: {config.selector.organization_id}")

    async for users in client.get_users(params):
        logger.info(f"Received user batch with {len(users)} users")
        yield users


@ocean.on_resync(Kinds.ORGANIZATION)
async def on_resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync organizations from Zendesk."""
    client = create_zendesk_client()
    
    params = {}
    config = typing.cast(ZendeskOrganizationResourceConfig, event.resource_config)
    
    # Apply filters based on selector configuration
    if config.selector.external_id:
        params["external_id"] = config.selector.external_id
        logger.info(f"Filtering organizations by external ID: {config.selector.external_id}")

    async for organizations in client.get_organizations(params):
        logger.info(f"Received organization batch with {len(organizations)} organizations")
        yield organizations


@ocean.on_resync(Kinds.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync groups from Zendesk."""
    client = create_zendesk_client()
    
    params = {}
    config = typing.cast(ZendeskGroupResourceConfig, event.resource_config)
    
    # Apply filters based on selector configuration
    if config.selector.include_deleted:
        params["include_deleted"] = config.selector.include_deleted
        logger.info(f"Including deleted groups: {config.selector.include_deleted}")

    async for groups in client.get_groups(params):
        logger.info(f"Received group batch with {len(groups)} groups")
        yield groups


@ocean.on_resync(Kinds.BRAND)
async def on_resync_brands(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync brands from Zendesk."""
    client = create_zendesk_client()
    
    params = {}
    config = typing.cast(ZendeskBrandResourceConfig, event.resource_config)
    
    # Apply filters based on selector configuration
    if not config.selector.active_only:
        params["active"] = False
        logger.info("Including inactive brands")

    async for brands in client.get_brands(params):
        logger.info(f"Received brand batch with {len(brands)} brands")
        yield brands


@ocean.on_start()
async def on_start() -> None:
    """Called when the integration starts."""
    logger.info("Starting Port Ocean Zendesk integration")
    
    # Test the connection
    client = create_zendesk_client()
    connection_ok = await client.test_connection()
    
    if not connection_ok:
        logger.error("Failed to connect to Zendesk API. Please check your configuration.")
        return
    
    # Skip webhook creation for ONCE event listener
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # TODO: Implement webhook creation
    logger.info("Webhook creation will be implemented in the next phase")


# Register webhook processors
ocean.add_webhook_processor("/webhook", TicketWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)
ocean.add_webhook_processor("/webhook", OrganizationWebhookProcessor)