"""
Main entry point for the Anthropic Ocean integration.

This module implements the core integration logic for syncing data from Anthropic API:
- API key information
- Usage metrics and token consumption  
- Cost data and billing information

Based on:
- Anthropic API documentation: https://docs.anthropic.com/en/api
- Usage and Cost API: https://docs.anthropic.com/en/api/usage-cost-api
- Ocean integration patterns

The integration handles:
- Authentication via API tokens
- Rate limiting and error handling
- Data transformation for Ocean/Port
- Incremental data fetching
"""

import datetime
from typing import cast
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import create_anthropic_client
from integration import (
    ObjectKind,
    AnthropicApiKeyConfig,
    AnthropicUsageConfig,
    AnthropicCostConfig,
)


@ocean.on_start()
async def on_start() -> None:
    """
    Initialize the Anthropic integration.
    
    This function:
    - Tests the API connection
    - Validates configuration
    - Sets up any required initialization
    
    Based on Ocean lifecycle patterns for integration startup.
    """
    logger.info("Starting Anthropic Ocean integration")
    
    try:
        # Test API connection on startup
        client = create_anthropic_client()
        connection_ok = await client.test_connection()
        
        if not connection_ok:
            logger.error("Failed to establish connection to Anthropic API")
            raise Exception("Anthropic API connection test failed")
            
        logger.info("Anthropic integration started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start Anthropic integration: {e}")
        raise


@ocean.on_resync(ObjectKind.API_KEY)
async def resync_api_keys(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync API key information from Anthropic.
    
    This function fetches API key data including:
    - Key metadata and permissions
    - Organization association
    - Usage permissions
    - Key status and creation info
    
    Based on Anthropic API structure and Ocean resync patterns.
    The API key data is synthetic since Anthropic doesn't expose
    comprehensive key listing endpoints for security reasons.
    
    Args:
        kind: The resource kind being synced ("api-key")
        
    Yields:
        Lists of API key data dictionaries
    """
    logger.info(f"Starting resync for kind: {kind}")
    
    try:
        client = create_anthropic_client()
        config = cast(AnthropicApiKeyConfig, event.resource_config)
        
        logger.info("Fetching API key information from Anthropic")
        
        async for api_keys in client.get_api_keys():
            logger.info(f"Retrieved {len(api_keys)} API key records")
            yield api_keys
            
    except Exception as e:
        logger.error(f"Failed to resync API keys: {e}")
        raise


@ocean.on_resync(ObjectKind.USAGE)
async def resync_usage_data(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync usage data from Anthropic Usage API.
    
    This function fetches usage metrics including:
    - Token consumption (input/output)
    - Message counts and processing time
    - Model-specific usage statistics
    - Time-series usage data
    - Workspace and service tier breakdown
    
    Based on: https://docs.anthropic.com/en/api/usage-cost-api
    Endpoint: /v1/organizations/usage_report/messages
    
    Expected data format:
    - Time-bucketed usage statistics
    - Input/output token counts per model
    - Cache hit rates and efficiency metrics
    - Request success/failure rates
    
    Args:
        kind: The resource kind being synced ("usage")
        
    Yields:
        Lists of usage data dictionaries with metrics and timestamps
    """
    logger.info(f"Starting resync for kind: {kind}")
    
    try:
        client = create_anthropic_client()
        config = cast(AnthropicUsageConfig, event.resource_config)
        selector = config.selector
        
        # Calculate date range based on selector configuration
        end_date = datetime.datetime.now(datetime.timezone.utc)
        start_date = end_date - datetime.timedelta(days=selector.days_back)
        
        logger.info(
            f"Fetching usage data from {start_date.isoformat()} to {end_date.isoformat()} "
            f"with time_bucket={selector.time_bucket}"
        )
        
        async for usage_data in client.get_usage_data(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            time_bucket=selector.time_bucket
        ):
            logger.info(f"Retrieved {len(usage_data)} usage records")
            yield usage_data
            
    except Exception as e:
        logger.error(f"Failed to resync usage data: {e}")
        raise


@ocean.on_resync(ObjectKind.COSTS)
async def resync_cost_data(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync cost data from Anthropic Cost API.
    
    This function fetches cost information including:
    - Daily cost breakdowns in USD
    - Token usage costs by model
    - Web search and code execution costs  
    - Workspace cost attribution
    - Service tier pricing details
    
    Based on: https://docs.anthropic.com/en/api/usage-cost-api
    Endpoint: /v1/organizations/cost_report
    
    Expected data format:
    - Daily cost summaries with USD amounts
    - Cost breakdown by service type (tokens, search, etc.)
    - Model-specific cost data
    - Workspace and project cost attribution
    
    Args:
        kind: The resource kind being synced ("costs")
        
    Yields:
        Lists of cost data dictionaries with amounts and breakdowns
    """
    logger.info(f"Starting resync for kind: {kind}")
    
    try:
        client = create_anthropic_client()
        config = cast(AnthropicCostConfig, event.resource_config)
        selector = config.selector
        
        # Calculate date range based on selector configuration  
        end_date = datetime.datetime.now(datetime.timezone.utc)
        start_date = end_date - datetime.timedelta(days=selector.days_back)
        
        logger.info(
            f"Fetching cost data from {start_date.isoformat()} to {end_date.isoformat()}"
        )
        
        async for cost_data in client.get_cost_data(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat()
        ):
            logger.info(f"Retrieved {len(cost_data)} cost records")
            yield cost_data
            
    except Exception as e:
        logger.error(f"Failed to resync cost data: {e}")
        raise