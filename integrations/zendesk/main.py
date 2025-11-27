from typing import cast

from loguru import logger
from initialize_client import create_zendesk_client
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook_processors.ticket_webhook_processor import TicketWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor
from webhook_processors.organization_webhook_processor import OrganizationWebhookProcessor

"""
Main integration handlers for Zendesk Ocean integration

Based on Ocean integration patterns and Zendesk API documentation:
- Tickets API: https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
- Side Conversations: https://developer.zendesk.com/api-reference/ticketing/side_conversation/side_conversation/
- Users API: https://developer.zendesk.com/api-reference/ticketing/users/users/
- Organizations API: https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/

Purpose: Implement resync handlers for all four supported domain objects
Expected output: Async generators yielding batches of Zendesk data for synchronization
"""


@ocean.on_resync(Kinds.TICKET)
async def on_resync_tickets(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync handler for Zendesk tickets
    
    Based on: https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
    
    Purpose: Fetch all tickets from Zendesk with pagination support
    Expected output: Async generator yielding batches of ticket data
    """
    client = create_zendesk_client()
    
    logger.info("Starting resync for Zendesk tickets")
    
    # Optional: Add any custom parameters from resource config
    params = {}
    
    async for tickets_batch in client.get_paginated_tickets(params):
        logger.info(f"Received ticket batch with {len(tickets_batch)} tickets")
        yield tickets_batch


@ocean.on_resync(Kinds.SIDE_CONVERSATION)
async def on_resync_side_conversations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync handler for Zendesk side conversations
    
    Based on: https://developer.zendesk.com/api-reference/ticketing/side_conversation/side_conversation/
    
    Purpose: Fetch all side conversations from all tickets
    Expected output: Async generator yielding batches of side conversation data
    """
    client = create_zendesk_client()
    
    logger.info("Starting resync for Zendesk side conversations")
    
    async for side_conversations_batch in client.get_all_side_conversations():
        logger.info(f"Received side conversations batch with {len(side_conversations_batch)} conversations")
        yield side_conversations_batch


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync handler for Zendesk users
    
    Based on: https://developer.zendesk.com/api-reference/ticketing/users/users/
    
    Purpose: Fetch all users (end-users, agents, admins) from Zendesk
    Expected output: Async generator yielding batches of user data
    """
    client = create_zendesk_client()
    
    logger.info("Starting resync for Zendesk users")
    
    # Optional: Add any custom parameters from resource config
    params = {}
    
    async for users_batch in client.get_paginated_users(params):
        logger.info(f"Received user batch with {len(users_batch)} users")
        yield users_batch


@ocean.on_resync(Kinds.ORGANIZATION)
async def on_resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync handler for Zendesk organizations
    
    Based on: https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/
    
    Purpose: Fetch all organizations from Zendesk
    Expected output: Async generator yielding batches of organization data
    """
    client = create_zendesk_client()
    
    logger.info("Starting resync for Zendesk organizations")
    
    # Optional: Add any custom parameters from resource config
    params = {}
    
    async for organizations_batch in client.get_paginated_organizations(params):
        logger.info(f"Received organization batch with {len(organizations_batch)} organizations")
        yield organizations_batch


# Called once when the integration starts
@ocean.on_start()
async def on_start() -> None:
    """
    Integration startup handler
    
    Purpose: Initialize the integration and test connectivity
    Expected output: Successful connection test and integration readiness
    """
    logger.info("Starting Port Ocean Zendesk integration")
    
    client = create_zendesk_client()
    
    # Test connection to Zendesk API
    if await client.test_connection():
        logger.info("Zendesk integration initialized successfully")
    else:
        logger.error("Failed to initialize Zendesk integration - connection test failed")
        raise Exception("Could not connect to Zendesk API")


# Register webhook processors for real-time updates
# Based on Zendesk webhook events documentation:
# https://developer.zendesk.com/api-reference/webhooks/event-types/webhook-event-types/
ocean.add_webhook_processor("/webhook", TicketWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)  
ocean.add_webhook_processor("/webhook", OrganizationWebhookProcessor)