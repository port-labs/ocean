import asyncio
import time
from typing import Any, AsyncGenerator, Optional
from urllib.parse import urljoin

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result

PAGE_SIZE = 100
MAXIMUM_CONCURRENT_REQUESTS = 10
DEFAULT_RATE_LIMIT_PER_HOUR = 3600  # Conservative default


class CheckmarxAuthenticationError(Exception):
    """Raised when authentication with Checkmarx One fails."""
    pass


class CheckmarxAPIError(Exception):
    """Raised when Checkmarx One API returns an error."""
    pass


class CheckmarxClient:
    """
    Client for interacting with Checkmarx One API.
    Supports both OAuth client and API key authentication methods.
    """

    def __init__(
        self,
        base_url: str,
        iam_url: str,
        tenant: str,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        rate_limiter: Optional[AsyncLimiter] = None,
    ):
        """
        Initialize the Checkmarx One client.

        Args:
            base_url: Base URL for API calls (e.g., https://ast.checkmarx.net)
            iam_url: IAM URL for authentication (e.g., https://iam.checkmarx.net)
            tenant: Tenant name for authentication
            api_key: API key for authentication
            client_id: OAuth client ID (alternative to API key)
            client_secret: OAuth client secret (required with client_id)
            rate_limiter: Custom rate limiter instance
        """
        self.base_url = base_url.rstrip("/")
        self.iam_url = iam_url.rstrip("/")
        self.tenant = tenant
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret

        # HTTP client setup
        self.http_client = http_async_client
        self.http_client.timeout = httpx.Timeout(30)

        # Rate limiting
        if rate_limiter is None:
            rate_limiter = AsyncLimiter(DEFAULT_RATE_LIMIT_PER_HOUR, 3600)
        self.rate_limiter = rate_limiter
        self._semaphore = asyncio.Semaphore(MAXIMUM_CONCURRENT_REQUESTS)

        # Token management
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

        # Validate authentication method
        if not self._validate_auth_method():
            raise CheckmarxAuthenticationError(
                "Either provide api_key or both client_id and client_secret for authentication"
            )

    def _validate_auth_method(self) -> bool:
        """Validate that at least one authentication method is provided."""
        api_key_provided = bool(self.api_key)
        oauth_provided = bool(self.client_id and self.client_secret)

        if not api_key_provided and not oauth_provided:
            return False

        if api_key_provided and oauth_provided:
            logger.warning("Both API key and OAuth credentials provided. Using API key authentication.")

        return True

    @property
    def auth_url(self) -> str:
        """Get the authentication URL for the tenant."""
        return f"{self.iam_url}/auth/realms/{self.tenant}/protocol/openid-connect/token"

    @property
    def is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self._token_expires_at:
            return True
        # Add 60 second buffer for token refresh
        return time.time() >= (self._token_expires_at - 60)

    async def _authenticate_with_api_key(self) -> dict[str, Any]:
        """Authenticate using API key (refresh token flow)."""
        logger.debug("Authenticating with API key")

        auth_data = {
            "grant_type": "refresh_token",
            "client_id": "ast-app",
            "refresh_token": self.api_key,
        }

        try:
            response = await self.http_client.post(
                self.auth_url,
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"API key authentication failed: {e.response.status_code} - {e.response.text}")
            raise CheckmarxAuthenticationError(f"API key authentication failed: {e.response.text}")

    async def _authenticate_with_oauth(self) -> dict[str, Any]:
        """Authenticate using OAuth client credentials."""
        logger.debug(f"Authenticating with OAuth client: {self.client_id}")

        auth_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = await self.http_client.post(
                self.auth_url,
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"OAuth authentication failed: {e.response.status_code} - {e.response.text}")
            raise CheckmarxAuthenticationError(f"OAuth authentication failed: {e.response.text}")

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the appropriate method."""
        try:
            if self.api_key:
                token_response = await self._authenticate_with_api_key()
            else:
                token_response = await self._authenticate_with_oauth()

            self._access_token = token_response["access_token"]
            self._refresh_token = token_response.get("refresh_token")

            # Token expires in seconds, store absolute time
            expires_in = token_response.get("expires_in", 1800)  # Default 30 minutes
            self._token_expires_at = time.time() + expires_in

            logger.info(f"Successfully refreshed access token, expires in {expires_in} seconds")

        except Exception as e:
            logger.error(f"Failed to refresh access token: {str(e)}")
            raise CheckmarxAuthenticationError(f"Token refresh failed: {str(e)}")

    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        if not self._access_token or self.is_token_expired:
            await self._refresh_access_token()

        return self._access_token

    @property
    async def auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests."""
        access_token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send a request to the Checkmarx One API with proper error handling.

        Args:
            endpoint: API endpoint path (e.g., "/projects")
            method: HTTP method
            params: Query parameters
            json_data: JSON body data

        Returns:
            API response as dictionary
        """
        url = urljoin(f"{self.base_url}/api", endpoint.lstrip("/"))

        async with self.rate_limiter:
            async with self._semaphore:
                try:
                    logger.debug(f"Making {method} request to {url}")

                    response = await self.http_client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json_data,
                        headers=await self.auth_headers,
                    )

                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    status_code = e.response.status_code
                    response_text = e.response.text

                    logger.error(f"HTTP error {status_code} for {method} {url}: {response_text}")

                    if status_code == 401:
                        # Try to refresh token once
                        logger.info("Received 401, attempting to refresh token")
                        try:
                            await self._refresh_access_token()
                            # Retry the request with new token
                            response = await self.http_client.request(
                                method=method,
                                url=url,
                                params=params,
                                json=json_data,
                                headers=await self.auth_headers,
                            )
                            response.raise_for_status()
                            return response.json()
                        except Exception:
                            raise CheckmarxAuthenticationError("Authentication failed after token refresh")

                    elif status_code == 403:
                        raise CheckmarxAPIError("Access denied. Please check your permissions.")
                    elif status_code == 404:
                        logger.warning(f"Resource not found: {url}")
                        return {}
                    elif status_code == 429:
                        logger.warning("Rate limit exceeded. Consider reducing request frequency.")
                        raise CheckmarxAPIError("Rate limit exceeded")
                    else:
                        raise CheckmarxAPIError(f"API request failed: {response_text}")

                except Exception as e:
                    logger.error(f"Unexpected error during API request to {url}: {str(e)}")
                    raise CheckmarxAPIError(f"Request failed: {str(e)}")

    async def _get_paginated_resources(
        self,
        endpoint: str,
        object_key: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get paginated resources from Checkmarx One API.

        Args:
            endpoint: API endpoint path
            params: Additional query parameters

        Yields:
            Batches of resources
        """
        if params is None:
            params = {}

        offset = 0

        while True:
            page_params = {
                **params,
                "limit": PAGE_SIZE,
                "offset": offset,
            }

            try:
                response = await self._send_api_request(endpoint, params=page_params)
                # Handle different response formats
                items = []
                if isinstance(response, list):
                    items = response
                elif isinstance(response, dict):
                    # Try common pagination patterns
                    items = (
                        response.get("data", []) or
                        response.get("items", []) or
                        response.get("results", []) or
                        response.get(object_key, []) or
                        []
                    )

                if not items:
                    break

                yield items

                # Check if we have more data
                if len(items) < PAGE_SIZE:
                    break

                offset += len(items)

            except Exception as e:
                logger.error(f"Error in paginated request to {endpoint}: {str(e)}")
                break

    async def get_projects(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get projects from Checkmarx One.

        Args:
            limit: Maximum number of projects per page
            offset: Starting offset for pagination

        Yields:
            Batches of projects
        """
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        async for projects in self._get_paginated_resources("/projects", "projects", params):
            logger.info(f"Fetched batch of {len(projects)} projects")
            yield projects

    async def get_scans(
        self,
        project_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get scans from Checkmarx One.

        Args:
            project_id: Filter scans by project ID
            limit: Maximum number of scans per page
            offset: Starting offset for pagination

        Yields:
            Batches of scans
        """
        params = {}
        if project_id:
            params["project-id"] = project_id
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset

        async for scans in self._get_paginated_resources("/scans", "scans", params):
            logger.info(f"Fetched batch of {len(scans)} scans")
            yield scans

    async def get_project_by_id(self, project_id: str) -> dict[str, Any]:
        """Get a specific project by ID."""
        response = await self._send_api_request(f"/projects/{project_id}")
        logger.info(f"Fetched project with ID: {project_id}")
        return response

    async def get_scan_by_id(self, scan_id: str) -> dict[str, Any]:
        """Get a specific scan by ID."""
        response = await self._send_api_request(f"/scans/{scan_id}")
        logger.info(f"Fetched scan with ID: {scan_id}")
        return response
