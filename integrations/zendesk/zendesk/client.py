import asyncio
import base64
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from httpx import AsyncClient, BasicAuth, Request, Response, Timeout
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

"""
Zendesk API client implementation based on official documentation:
- API Reference: https://developer.zendesk.com/api-reference/introduction/introduction/
- Rate Limits: https://developer.zendesk.com/api-reference/introduction/rate-limits/
- Authentication: https://developer.zendesk.com/api-reference/introduction/security-and-auth/

Purpose: Provide a comprehensive client to interact with Zendesk's REST API
Expected output: Authenticated HTTP client with rate limiting and pagination support
"""

PAGE_SIZE = 100
MAX_CONCURRENT_REQUESTS = 5
DEFAULT_TIMEOUT = 30


class ZendeskClient:
    """
    Zendesk API client supporting API token authentication with rate limiting
    
    Based on Zendesk API documentation:
    - Uses API token authentication (preferred over basic auth)
    - Implements rate limiting per https://developer.zendesk.com/api-reference/introduction/rate-limits/
    - Supports pagination for large datasets
    - Handles the four main domain objects: tickets, side_conversations, users, and organizations
    """
    
    def __init__(
        self,
        subdomain: str,
        email: str,
        api_token: str,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize Zendesk client with API token authentication
        
        Args:
            subdomain: Zendesk subdomain (e.g., 'mycompany' for mycompany.zendesk.com)
            email: User email address
            api_token: API token from Zendesk admin center
            timeout: Request timeout in seconds
        """
        self.subdomain = subdomain
        self.email = email
        self.api_token = api_token
        self.base_url = f"https://{subdomain}.zendesk.com"
        
        # API token authentication format: {email}/token:{api_token}
        # Based on: https://developer.zendesk.com/api-reference/introduction/security-and-auth/
        auth_string = f"{email}/token:{api_token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        self.headers = {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        self.timeout = Timeout(timeout)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated HTTP request to Zendesk API with rate limiting
        
        Based on Zendesk rate limits documentation:
        https://developer.zendesk.com/api-reference/introduction/rate-limits/
        
        Purpose: Handle HTTP requests with proper authentication and error handling
        Expected output: JSON response from Zendesk API
        """
        url = urljoin(f"{self.base_url}/api/v2/", endpoint.lstrip("/"))
        
        async with self._semaphore:
            try:
                async with http_async_client.get_client() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        params=params,
                        json=json_data,
                        timeout=self.timeout
                    )
                    
                    # Handle rate limiting (HTTP 429)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited. Waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        return await self._make_request(method, endpoint, params, json_data)
                    
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                raise

    async def _paginate(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        items_key: str = "results"
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Handle pagination for Zendesk API endpoints
        
        Purpose: Efficiently paginate through large datasets
        Expected output: Async generator yielding batches of items
        """
        if params is None:
            params = {}
        
        params["per_page"] = PAGE_SIZE
        next_url = endpoint
        
        while next_url:
            response = await self._make_request("GET", next_url, params)
            
            items = response.get(items_key, [])
            if items:
                yield items
            
            # Handle Zendesk pagination
            next_url = response.get("next_page")
            if next_url:
                # Extract endpoint from full URL
                next_url = next_url.replace(f"{self.base_url}/api/v2/", "")
                params = {}  # URL already contains params

    # Ticket-related methods
    # Based on: https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
    async def get_paginated_tickets(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Retrieve paginated tickets from Zendesk
        
        Purpose: Fetch all tickets with optional filtering
        Expected output: Batches of ticket data as dictionaries
        """
        async for tickets in self._paginate("tickets", params, "tickets"):
            logger.info(f"Retrieved {len(tickets)} tickets")
            yield tickets

    async def get_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """Get single ticket by ID"""
        response = await self._make_request("GET", f"tickets/{ticket_id}")
        return response["ticket"]

    # Side conversation methods
    # Based on: https://developer.zendesk.com/api-reference/ticketing/side_conversation/side_conversation/
    async def get_paginated_side_conversations_for_ticket(
        self, ticket_id: int
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Retrieve side conversations for a specific ticket
        
        Purpose: Get side conversations associated with a ticket
        Expected output: List of side conversation data
        """
        endpoint = f"tickets/{ticket_id}/side_conversations"
        try:
            response = await self._make_request("GET", endpoint)
            side_conversations = response.get("side_conversations", [])
            if side_conversations:
                yield side_conversations
        except Exception as e:
            logger.warning(f"Failed to get side conversations for ticket {ticket_id}: {e}")

    async def get_all_side_conversations(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get all side conversations by iterating through tickets
        
        Purpose: Collect all side conversations from all tickets
        Expected output: Batches of side conversation data
        """
        # Since there's no direct endpoint to get all side conversations,
        # we need to get them through tickets
        async for tickets in self.get_paginated_tickets():
            all_side_conversations = []
            
            for ticket in tickets:
                ticket_id = ticket["id"]
                async for side_conversations in self.get_paginated_side_conversations_for_ticket(ticket_id):
                    # Add ticket_id to each side conversation for context
                    for conversation in side_conversations:
                        conversation["ticket_id"] = ticket_id
                    all_side_conversations.extend(side_conversations)
            
            if all_side_conversations:
                yield all_side_conversations

    # User-related methods  
    # Based on: https://developer.zendesk.com/api-reference/ticketing/users/users/
    async def get_paginated_users(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Retrieve paginated users from Zendesk
        
        Purpose: Fetch all users (end-users, agents, admins)
        Expected output: Batches of user data as dictionaries
        """
        async for users in self._paginate("users", params, "users"):
            logger.info(f"Retrieved {len(users)} users")
            yield users

    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get single user by ID"""
        response = await self._make_request("GET", f"users/{user_id}")
        return response["user"]

    async def search_users(self, query: str) -> List[Dict[str, Any]]:
        """Search users by query"""
        params = {"query": query}
        response = await self._make_request("GET", "users/search", params)
        return response.get("users", [])

    # Organization-related methods
    # Based on: https://developer.zendesk.com/api-reference/ticketing/organizations/organizations/
    async def get_paginated_organizations(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Retrieve paginated organizations from Zendesk
        
        Purpose: Fetch all organizations
        Expected output: Batches of organization data as dictionaries
        """
        async for organizations in self._paginate("organizations", params, "organizations"):
            logger.info(f"Retrieved {len(organizations)} organizations")
            yield organizations

    async def get_organization(self, org_id: int) -> Dict[str, Any]:
        """Get single organization by ID"""
        response = await self._make_request("GET", f"organizations/{org_id}")
        return response["organization"]

    # Health check method
    async def test_connection(self) -> bool:
        """
        Test the connection to Zendesk API
        
        Purpose: Verify authentication and connectivity
        Expected output: Boolean indicating successful connection
        """
        try:
            await self._make_request("GET", "users/me")
            logger.info("Successfully connected to Zendesk API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zendesk API: {e}")
            return False