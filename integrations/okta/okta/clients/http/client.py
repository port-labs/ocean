"""Okta API client implementation."""

import asyncio
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from httpx import Response

logger = logging.getLogger(__name__)


class OktaClient:
    """Okta API client."""

    # Okta uses Link headers for pagination
    NEXT_PATTERN = re.compile(r'<([^>]+)>; rel="next"')
    PAGE_SIZE = 200  # Okta's default page size

    def __init__(
        self,
        okta_domain: str,
        api_token: str,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Initialize the Okta client.

        Args:
            okta_domain: The Okta domain (e.g., 'dev-123456.okta.com')
            api_token: The Okta API token
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.okta_domain = okta_domain.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self.max_retries = max_retries
        
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"SSWS {api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Port-Ocean-Okta-Integration/1.0",
            },
        )

    @property
    def base_url(self) -> str:
        """Get the base URL for Okta API."""
        return f"https://{self.okta_domain}/api/v1"

    async def make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make an HTTP request to the Okta API.

        Args:
            endpoint: The API endpoint (e.g., '/users')
            method: HTTP method (GET, POST, PUT, DELETE)
            params: Query parameters
            json_data: JSON payload for POST/PUT requests
            headers: Additional headers

        Returns:
            HTTP response object

        Raises:
            httpx.HTTPError: If the request fails after all retries
        """
        # Build URL safely without losing "/api/v1" segment
        normalized_endpoint = endpoint.lstrip("/")
        base = self.base_url.rstrip("/")
        url = f"{base}/{normalized_endpoint}"
        
        request_headers = self._client.headers.copy()
        if headers:
            request_headers.update(headers)

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Making {method} request to {url} (attempt {attempt + 1})")
                
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                )
                
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < self.max_retries:  # Rate limited
                    retry_after = int(e.response.headers.get("Retry-After", 1))
                    logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                    await asyncio.sleep(retry_after)
                    continue
                
                logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
                raise
                
            except httpx.RequestError as e:
                if attempt < self.max_retries:
                    logger.warning(f"Request failed, retrying: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                
                logger.error(f"Request failed after {self.max_retries + 1} attempts: {e}")
                raise

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _get_next_link(self, link_header: str) -> Optional[str]:
        """Extract the URL from the 'next' link in an Okta Link header."""
        match = self.NEXT_PATTERN.search(link_header)
        return match.group(1) if match else None

    async def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle Okta's pagination for API requests.

        Args:
            endpoint: The API endpoint
            params: Query parameters
            method: HTTP method

        Yields:
            List of items from each page
        """
        if params is None:
            params = {}

        # Set page size for optimal performance
        params["limit"] = self.PAGE_SIZE

        logger.info(f"Starting pagination for {method} {endpoint}")

        while True:
            response = await self.make_request(
                endpoint,
                method=method,
                params=params,
            )

            if not response or not (items := response.json()):
                break

            yield items

            # Check for next page using Link header
            if not (link_header := response.headers.get("Link")) or not (
                next_url := self._get_next_link(link_header)
            ):
                break

            # Extract endpoint from next URL
            endpoint = next_url.replace(self.base_url.rstrip("/"), "").lstrip("/")
            params = None  # Reset params as they're included in the next URL

    async def get_users(
        self,
        search: Optional[str] = None,
        filter_query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get users with pagination support.

        Args:
            search: Search query for users
            filter_query: Filter expression for users
            limit: Maximum number of users to return

        Yields:
            List of users from each page
        """
        params = {}
        if search:
            params["search"] = search
        if filter_query:
            params["filter"] = filter_query
        if limit:
            params["limit"] = min(limit, self.PAGE_SIZE)

        async for users in self.send_paginated_request("users", params=params):
            yield users

    async def get_groups(
        self,
        search: Optional[str] = None,
        filter_query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get groups with pagination support.

        Args:
            search: Search query for groups
            filter_query: Filter expression for groups
            limit: Maximum number of groups to return

        Yields:
            List of groups from each page
        """
        params = {}
        if search:
            params["search"] = search
        if filter_query:
            params["filter"] = filter_query
        if limit:
            params["limit"] = min(limit, self.PAGE_SIZE)

        async for groups in self.send_paginated_request("groups", params=params):
            yield groups

    async def get_applications(
        self,
        search: Optional[str] = None,
        filter_query: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get applications with pagination support.

        Args:
            search: Search query for applications
            filter_query: Filter expression for applications
            limit: Maximum number of applications to return

        Yields:
            List of applications from each page
        """
        params = {}
        if search:
            params["q"] = search
        if filter_query:
            params["filter"] = filter_query
        if limit:
            params["limit"] = min(limit, self.PAGE_SIZE)

        async for apps in self.send_paginated_request("apps", params=params):
            yield apps

    async def get_user_groups(self, user_id: str) -> List[Dict[str, Any]]:
        """Get groups for a specific user.

        Args:
            user_id: The user ID

        Returns:
            List of groups for the user
        """
        response = await self.make_request(f"users/{user_id}/groups")
        return response.json() if response else []

    async def get_user_apps(self, user_id: str) -> List[Dict[str, Any]]:
        """Get applications for a specific user.

        Args:
            user_id: The user ID

        Returns:
            List of applications for the user
        """
        response = await self.make_request(f"users/{user_id}/appLinks")
        return response.json() if response else []

    async def get_group_members(self, group_id: str) -> List[Dict[str, Any]]:
        """Get members of a specific group.

        Args:
            group_id: The group ID

        Returns:
            List of group members
        """
        response = await self.make_request(f"/groups/{group_id}/users")
        return response.json() if response else []

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """Get a specific user by ID.

        Args:
            user_id: The user ID

        Returns:
            User data
        """
        endpoint = f"users/{user_id}"
        response = await self.make_request(endpoint)
        return response.json()

    async def get_group(self, group_id: str) -> Dict[str, Any]:
        """Get a specific group by ID.

        Args:
            group_id: The group ID

        Returns:
            Group data
        """
        endpoint = f"groups/{group_id}"
        response = await self.make_request(endpoint)
        return response.json()

    async def get_application(self, app_id: str) -> Dict[str, Any]:
        """Get a specific application by ID.

        Args:
            app_id: The application ID

        Returns:
            Application data
        """
        endpoint = f"apps/{app_id}"
        response = await self.make_request(endpoint)
        return response.json()

    async def get_application_users(self, app_id: str) -> List[Dict[str, Any]]:
        """Get users assigned to a specific application.

        Args:
            app_id: The application ID

        Returns:
            List of application users
        """
        endpoint = f"apps/{app_id}/users"
        users = []
        async for user_batch in self.send_paginated_request(endpoint):
            users.extend(user_batch)
        return users

