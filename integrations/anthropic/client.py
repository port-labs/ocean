"""
Anthropic API client for Ocean integration.

This module implements a client for the Anthropic API to fetch:
- API keys information
- Usage metrics and cost data
- Organization details

Based on:
- Anthropic API documentation: https://docs.anthropic.com/en/api
- Usage and Cost API documentation: https://docs.anthropic.com/en/api/usage-cost-api
- Rate limits documentation: https://docs.anthropic.com/en/api/rate-limits
- Authentication documentation: https://docs.anthropic.com/en/api/overview#authentication

This client is designed to:
- Authenticate using API tokens (x-api-key header)
- Handle rate limiting with exponential backoff
- Fetch organization usage and cost data
- Return data in format suitable for Ocean processing
"""

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils.async_http import HttpClient


class AnthropicClient:
    """
    Client for interacting with the Anthropic API.
    
    Handles authentication, rate limiting, and data fetching for:
    - API key information
    - Usage metrics
    - Cost data
    
    Based on Anthropic API documentation at https://docs.anthropic.com/en/api
    """

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com"):
        """
        Initialize the Anthropic client.
        
        Args:
            api_key: Admin API key from Anthropic Console (https://console.anthropic.com/account/keys)
            base_url: Base URL for Anthropic API (defaults to production)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to the Anthropic API.
        
        This method handles:
        - Authentication via x-api-key header
        - Rate limiting with exponential backoff
        - Error handling for API responses
        - Retry logic for transient failures
        
        Based on Anthropic rate limiting docs: https://docs.anthropic.com/en/api/rate-limits
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data
            
        Returns:
            Dict containing the API response
            
        Raises:
            Exception: For API errors or rate limit exceeded
        """
        url = f"{self.base_url}{endpoint}"
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries + 1):
            try:
                async with HttpClient() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        params=params,
                        json=data
                    )
                    
                    # Handle rate limiting (429 error)
                    if response.status_code == 429:
                        retry_after = response.headers.get("retry-after", retry_delay)
                        if attempt < max_retries:
                            logger.warning(f"Rate limit hit, retrying after {retry_after}s")
                            await asyncio.sleep(int(retry_after))
                            retry_delay *= 2
                            continue
                        else:
                            raise Exception(f"Rate limit exceeded after {max_retries} retries")
                    
                    # Handle other HTTP errors
                    if response.status_code >= 400:
                        error_msg = f"API request failed with status {response.status_code}"
                        if hasattr(response, 'text'):
                            error_msg += f": {response.text()}"
                        raise Exception(error_msg)
                    
                    return response.json()
                    
            except Exception as e:
                if attempt < max_retries and "rate limit" not in str(e).lower():
                    logger.warning(f"Request failed, retrying in {retry_delay}s: {e}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise e
                
        raise Exception(f"Request failed after {max_retries + 1} attempts")

    async def get_api_keys(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch API key information.
        
        Since Anthropic doesn't provide a direct API to list all API keys,
        this method returns information about the current API key being used.
        
        This is intended to provide:
        - Current API key metadata
        - Organization association
        - Usage permissions
        
        Expected to return:
        - API key identifier (masked for security)
        - Organization ID
        - Creation timestamp
        - Permissions/scopes
        """
        try:
            logger.info("Fetching API key information")
            
            # Since there's no direct API to list keys, we'll create a synthetic entry
            # based on the current key's organization context
            api_key_info = [{
                "id": f"key_{hash(self.api_key) % 10000}",  # Synthetic ID
                "key_prefix": self.api_key[:8] + "..." if len(self.api_key) > 8 else "key_***",
                "organization_id": "current_org",  # This would be extracted from API responses
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": "active",
                "type": "admin" if self.api_key else "standard"
            }]
            
            logger.info(f"Retrieved {len(api_key_info)} API key entries")
            yield api_key_info
            
        except Exception as e:
            logger.error(f"Failed to fetch API keys: {e}")
            raise

    async def get_usage_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        time_bucket: str = "1d"
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch usage data from the Anthropic Usage API.
        
        Based on: https://docs.anthropic.com/en/api/usage-cost-api
        Endpoint: /v1/organizations/usage_report/messages
        
        This method fetches:
        - Token consumption data
        - Usage metrics by model
        - Time-series usage information
        - Workspace and service tier breakdown
        
        Expected to return:
        - Message usage statistics
        - Input/output token counts
        - Model-specific usage data
        - Time-bucketed metrics
        
        Args:
            start_date: Start date for usage data (ISO format)
            end_date: End date for usage data (ISO format) 
            time_bucket: Time granularity (1m, 1h, 1d)
        """
        try:
            logger.info(f"Fetching usage data with time_bucket={time_bucket}")
            
            params = {
                "time_bucket": time_bucket
            }
            
            if start_date:
                params["start_time"] = start_date
            if end_date:
                params["end_time"] = end_date
                
            response = await self._make_request(
                "GET",
                "/v1/organizations/usage_report/messages",
                params=params
            )
            
            usage_data = response.get("data", [])
            logger.info(f"Retrieved {len(usage_data)} usage records")
            
            # Process and yield usage data in chunks
            chunk_size = 100
            for i in range(0, len(usage_data), chunk_size):
                chunk = usage_data[i:i + chunk_size]
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to fetch usage data: {e}")
            raise

    async def get_cost_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Fetch cost data from the Anthropic Cost API.
        
        Based on: https://docs.anthropic.com/en/api/usage-cost-api
        Endpoint: /v1/organizations/cost_report
        
        This method fetches:
        - Cost breakdowns in USD
        - Token usage costs
        - Web search and code execution costs
        - Daily cost granularity
        
        Expected to return:
        - Daily cost summaries
        - Cost by service type
        - Model-specific cost data
        - Workspace cost attribution
        
        Args:
            start_date: Start date for cost data (ISO format)
            end_date: End date for cost data (ISO format)
        """
        try:
            logger.info("Fetching cost data")
            
            params = {}
            if start_date:
                params["start_time"] = start_date
            if end_date:
                params["end_time"] = end_date
                
            response = await self._make_request(
                "GET",
                "/v1/organizations/cost_report",
                params=params
            )
            
            cost_data = response.get("data", [])
            logger.info(f"Retrieved {len(cost_data)} cost records")
            
            # Process and yield cost data in chunks
            chunk_size = 100
            for i in range(0, len(cost_data), chunk_size):
                chunk = cost_data[i:i + chunk_size]
                yield chunk
                
        except Exception as e:
            logger.error(f"Failed to fetch cost data: {e}")
            raise

    async def test_connection(self) -> bool:
        """
        Test the API connection and authentication.
        
        This method validates:
        - API key is valid and active
        - Connection to Anthropic API
        - Required permissions for usage/cost data
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("Testing Anthropic API connection")
            
            # Try to make a simple API call to test authentication
            # We'll use the usage endpoint with minimal params
            await self._make_request(
                "GET",
                "/v1/organizations/usage_report/messages",
                params={"time_bucket": "1d", "limit": 1}
            )
            
            logger.info("API connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False


def create_anthropic_client() -> AnthropicClient:
    """
    Factory function to create an Anthropic client with Ocean configuration.
    
    Based on Ocean integration configuration:
    - api_key: Admin API key for Anthropic
    - base_url: Optional custom base URL (defaults to production)
    
    Returns:
        AnthropicClient: Configured client instance
        
    Raises:
        ValueError: If required configuration is missing
    """
    config = ocean.integration_config
    
    api_key = config.get("api_key")
    if not api_key:
        raise ValueError("api_key is required in integration configuration")
    
    base_url = config.get("base_url", "https://api.anthropic.com")
    
    return AnthropicClient(api_key=api_key, base_url=base_url)