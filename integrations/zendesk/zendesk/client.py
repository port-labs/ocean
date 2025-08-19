import asyncio
import base64
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urljoin

import httpx
from httpx import Auth, Request, Response, Timeout
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

PAGE_SIZE = 100
MAX_CONCURRENT_REQUESTS = 10


class ZendeskBasicAuth(Auth):
    """Basic auth using email/token or email/password format for Zendesk API."""
    
    def __init__(self, email: str, token: str) -> None:
        self.email = email
        self.token = token

    def auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        # Zendesk API token authentication uses email/token:api_token format
        credentials = f"{self.email}/token:{self.token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        request.headers["Authorization"] = f"Basic {encoded_credentials}"
        yield request


class ZendeskBearerAuth(Auth):
    """Bearer token auth for OAuth tokens."""
    
    def __init__(self, token: str) -> None:
        self.token = token

    def auth_flow(self, request: Request) -> AsyncGenerator[Request, Response]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class ZendeskClient:
    """Zendesk API client with support for both API tokens and OAuth."""
    
    def __init__(
        self, 
        subdomain: str, 
        email: Optional[str] = None, 
        token: Optional[str] = None,
        oauth_token: Optional[str] = None
    ) -> None:
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.zendesk.com"
        self.api_url = f"{self.base_url}/api/v2"
        
        # Setup authentication
        if oauth_token:
            self.auth = ZendeskBearerAuth(oauth_token)
        elif email and token:
            self.auth = ZendeskBasicAuth(email, token)
        else:
            raise ValueError("Must provide either oauth_token or both email and token")
        
        self.client = http_async_client
        self.client.auth = self.auth
        self.client.timeout = Timeout(30)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Send API request with rate limiting and error handling."""
        url = urljoin(f"{self.api_url}/", endpoint.lstrip("/"))
        
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method, 
                    url=url, 
                    params=params, 
                    json=json_data, 
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            await self._handle_rate_limit(e.response)
            logger.error(
                f"Zendesk API request failed with status {e.response.status_code}: {method} {url}"
            )
            if e.response.status_code == 401:
                logger.error("Authentication failed. Please check your credentials.")
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Zendesk API: {method} {url} - {str(e)}")
            raise

    async def _handle_rate_limit(self, response: Response) -> None:
        """Handle rate limiting with proper retry logic."""
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                wait_time = int(retry_after)
                logger.warning(
                    f"Zendesk API rate limit reached. Waiting for {wait_time} seconds."
                )
                await asyncio.sleep(wait_time)

    async def _get_paginated_data(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        extract_key: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated data from Zendesk API."""
        params = params or {}
        params.setdefault("per_page", PAGE_SIZE)
        
        next_page = None
        page = 1
        
        while True:
            if next_page:
                # Use the next_page URL directly
                url = next_page
                current_params = None
            else:
                url = endpoint
                current_params = {**params, "page": page}
            
            if next_page:
                # For next_page URLs, we make a direct request without base URL
                response = await self.client.get(next_page)
                response.raise_for_status()
                response_data = response.json()
            else:
                response_data = await self._send_api_request("GET", url, params=current_params)
            
            items = response_data.get(extract_key, []) if extract_key else response_data
            
            if not items:
                break
                
            yield items
            
            # Check for next page
            next_page = response_data.get("next_page")
            if not next_page:
                break
            
            page += 1

    async def get_tickets(
        self, 
        params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated tickets from Zendesk."""
        logger.info("Fetching tickets from Zendesk")
        async for tickets in self._get_paginated_data("tickets.json", params, "tickets"):
            yield tickets

    async def get_users(
        self, 
        params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated users from Zendesk."""
        logger.info("Fetching users from Zendesk")
        async for users in self._get_paginated_data("users.json", params, "users"):
            yield users

    async def get_organizations(
        self, 
        params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated organizations from Zendesk."""
        logger.info("Fetching organizations from Zendesk")
        async for organizations in self._get_paginated_data("organizations.json", params, "organizations"):
            yield organizations

    async def get_groups(
        self, 
        params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated groups from Zendesk."""
        logger.info("Fetching groups from Zendesk")
        async for groups in self._get_paginated_data("groups.json", params, "groups"):
            yield groups

    async def get_brands(
        self, 
        params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated brands from Zendesk."""
        logger.info("Fetching brands from Zendesk")
        async for brands in self._get_paginated_data("brands.json", params, "brands"):
            yield brands

    async def get_single_ticket(self, ticket_id: int) -> dict[str, Any]:
        """Get a single ticket by ID."""
        response = await self._send_api_request("GET", f"tickets/{ticket_id}.json")
        return response.get("ticket", {})

    async def get_single_user(self, user_id: int) -> dict[str, Any]:
        """Get a single user by ID."""
        response = await self._send_api_request("GET", f"users/{user_id}.json")
        return response.get("user", {})

    async def get_single_organization(self, organization_id: int) -> dict[str, Any]:
        """Get a single organization by ID."""
        response = await self._send_api_request("GET", f"organizations/{organization_id}.json")
        return response.get("organization", {})

    async def get_single_group(self, group_id: int) -> dict[str, Any]:
        """Get a single group by ID."""
        response = await self._send_api_request("GET", f"groups/{group_id}.json")
        return response.get("group", {})

    async def create_webhook(self, webhook_url: str, events: list[str]) -> dict[str, Any]:
        """Create a webhook for real-time updates."""
        webhook_data = {
            "webhook": {
                "name": f"Port Ocean Webhook - {ocean.config.integration.identifier}",
                "endpoint": webhook_url,
                "http_method": "POST",
                "status": "active",
                "subscriptions": events,
            }
        }
        
        logger.info(f"Creating Zendesk webhook: {webhook_url}")
        response = await self._send_api_request("POST", "webhooks.json", json_data=webhook_data)
        return response.get("webhook", {})

    async def list_webhooks(self) -> list[dict[str, Any]]:
        """List existing webhooks."""
        response = await self._send_api_request("GET", "webhooks.json")
        return response.get("webhooks", [])

    async def test_connection(self) -> bool:
        """Test the connection to Zendesk API."""
        try:
            await self._send_api_request("GET", "users/me.json")
            logger.info("Successfully connected to Zendesk API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Zendesk API: {e}")
            return False