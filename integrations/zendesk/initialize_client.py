from typing import Optional

from loguru import logger
from port_ocean.context.ocean import ocean

from zendesk.client import ZendeskClient

"""
Client initialization based on Ocean integration patterns
and Zendesk authentication documentation:
https://developer.zendesk.com/api-reference/introduction/security-and-auth/

Purpose: Initialize and configure Zendesk API client with proper authentication
Expected output: Configured ZendeskClient instance ready for API calls
"""


def create_zendesk_client() -> ZendeskClient:
    """
    Create a Zendesk client instance with API token authentication
    
    Based on Ocean integration config patterns and Zendesk auth documentation.
    Uses API token authentication as recommended over basic auth.
    
    Returns:
        ZendeskClient: Configured client instance
        
    Raises:
        ValueError: If required configuration is missing
    """
    
    # Get configuration from Ocean integration config
    subdomain = ocean.integration_config.get("subdomain")
    email = ocean.integration_config.get("email")
    api_token = ocean.integration_config.get("api_token")
    
    # Validate required configuration
    if not subdomain:
        raise ValueError("Zendesk subdomain is required")
    if not email:
        raise ValueError("Email is required for API token authentication")
    if not api_token:
        raise ValueError("API token is required")
    
    # Optional timeout configuration
    timeout = ocean.integration_config.get("timeout", 30)
    
    logger.info(f"Initializing Zendesk client for subdomain: {subdomain}")
    
    client = ZendeskClient(
        subdomain=subdomain,
        email=email,
        api_token=api_token,
        timeout=timeout
    )
    
    return client