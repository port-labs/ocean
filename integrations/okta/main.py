import typing
from typing import cast

from loguru import logger
from initialize_client import create_okta_client
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from okta.overrides import (
    OktaUserResourceConfig,
    OktaGroupResourceConfig,
    OktaRoleResourceConfig,
    OktaPermissionResourceConfig,
)


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Okta users"""
    client = create_okta_client()
    
    config = cast(OktaUserResourceConfig, event.resource_config)
    params = {}
    
    if config.selector.filter:
        params["filter"] = config.selector.filter
        logger.info(f"Found user filter: {config.selector.filter}")
    
    if config.selector.limit:
        params["limit"] = config.selector.limit
        
    async for users in client.get_paginated_users(params):
        logger.info(f"Received user batch with {len(users)} users")
        yield users


@ocean.on_resync(Kinds.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Okta groups"""
    client = create_okta_client()
    
    config = cast(OktaGroupResourceConfig, event.resource_config)
    params = {}
    
    if config.selector.filter:
        params["filter"] = config.selector.filter
        logger.info(f"Found group filter: {config.selector.filter}")
        
    if config.selector.limit:
        params["limit"] = config.selector.limit
        
    if config.selector.expand:
        params["expand"] = config.selector.expand
        
    async for groups in client.get_paginated_groups(params):
        logger.info(f"Received group batch with {len(groups)} groups")
        
        # Enrich groups with members if requested
        if config.selector.include_members:
            groups = await client.enrich_groups_with_members(groups)
            
        yield groups


@ocean.on_resync(Kinds.ROLE)
async def on_resync_roles(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Okta roles"""
    client = create_okta_client()
    
    config = cast(OktaRoleResourceConfig, event.resource_config)
    params = {}
    
    if config.selector.filter:
        params["filter"] = config.selector.filter
        logger.info(f"Found role filter: {config.selector.filter}")
        
    if config.selector.limit:
        params["limit"] = config.selector.limit
        
    async for roles in client.get_paginated_roles(params):
        logger.info(f"Received role batch with {len(roles)} roles")
        yield roles


@ocean.on_resync(Kinds.PERMISSION)
async def on_resync_permissions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Okta permissions (role assignments)"""
    client = create_okta_client()
    
    config = cast(OktaPermissionResourceConfig, event.resource_config)
    params = {}
    
    if config.selector.filter:
        params["filter"] = config.selector.filter
        logger.info(f"Found permission filter: {config.selector.filter}")
        
    if config.selector.limit:
        params["limit"] = config.selector.limit
        
    async for permissions in client.get_paginated_permissions(params):
        logger.info(f"Received permission batch with {len(permissions)} permissions")
        yield permissions


@ocean.on_resync(Kinds.APPLICATION)
async def on_resync_applications(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Okta applications"""
    client = create_okta_client()
    
    params = {}
    
    async for applications in client.get_paginated_applications(params):
        logger.info(f"Received application batch with {len(applications)} applications")
        yield applications


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Okta integration")
    
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook setup because the event listener is ONCE")
        return