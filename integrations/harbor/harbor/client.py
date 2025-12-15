"""Harbor API client for interacting with Harbor Registry."""

import asyncio
from typing import Any, AsyncGenerator, Optional

from httpx import BasicAuth, HTTPStatusError, RequestError, Timeout
from loguru import logger

from port_ocean.utils import http_async_client

# Constants for API configuration
MAX_CONCURRENT_REQUESTS = 10
PAGE_SIZE = 50
DEFAULT_TIMEOUT = 30


class HarborClient:
    """
    Client for interacting with the Harbor Registry API.
    
    This client handles:
    - API authentication (Basic Auth or no auth)
    - Rate limiting through semaphores
    - Pagination for resource fetching
    - Error handling and retries
    
    Attributes:
        base_url: Base URL of the Harbor instance
        client: HTTP client for making requests
    """

    def __init__(
        self,
        base_url: str,
        verify_ssl: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        Initialize the Harbor client.
        
        Args:
            base_url: Base URL of the Harbor instance (e.g., https://harbor.example.com)
            verify_ssl: Whether to verify SSL certificates
            username: Username for Basic Auth (optional)
            password: Password for Basic Auth (optional)
        """
        self.base_url = base_url.rstrip("/")
        self.client = http_async_client
        self.client.timeout = Timeout(DEFAULT_TIMEOUT)
        self.client.verify = verify_ssl
        
        # Configure authentication
        self._configure_authentication(username, password)
        
        # Rate limiting semaphore
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def _configure_authentication(
        self, 
        username: Optional[str], 
        password: Optional[str]
    ) -> None:
        """
        Configure client authentication based on provided credentials.
        
        Args:
            username: Username for Basic Auth
            password: Password for Basic Auth
        """
        if username and password:
            self.client.auth = BasicAuth(username, password)
            logger.debug("Harbor client configured with Basic Auth")
        else:
            logger.debug("Harbor client configured without authentication")

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """
        Send an HTTP request to the Harbor API.
        
        This method handles:
        - Rate limiting via semaphore
        - Automatic retry on 429 (rate limit) errors
        - Error logging
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint path (will be appended to base_url)
            params: Optional query parameters
            json_data: Optional JSON request body
            headers: Optional additional headers
        
        Returns:
            JSON response from the API
        
        Raises:
            HTTPStatusError: For HTTP error responses (except 429 which is retried)
            RequestError: For connection/request errors
        """
        # Construct full URL
        url = f"{self.base_url}{endpoint}" if not endpoint.startswith("http") else endpoint

        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

        except HTTPStatusError as e:
            if e.response.status_code == 429:
                # Handle rate limiting with retry
                retry_after = int(e.response.headers.get("Retry-After", "60"))
                logger.warning(
                    f"Rate limited (429) for {method} {endpoint}. "
                    f"Retrying after {retry_after} seconds."
                )
                await asyncio.sleep(retry_after)
                return await self._send_api_request(
                    method, endpoint, params, json_data, headers
                )
            
            logger.error(
                f"HTTP error for {method} {endpoint}: "
                f"Status {e.response.status_code}, Response: {e.response.text}"
            )
            raise
            
        except RequestError as e:
            logger.error(f"Request failed: {method} {endpoint} - {str(e)}")
            raise

    async def get_paginated_resources(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch paginated data from the Harbor API.
        
        Harbor uses page-based pagination with 'page' and 'page_size' parameters.
        This method yields batches of resources until all pages are exhausted.
        
        Args:
            endpoint: API endpoint path
            params: Optional query parameters (will be merged with pagination params)
            page_size: Number of items per page
        
        Yields:
            Lists of resource dictionaries for each page
        """
        if params is None:
            params = {}

        page = 1
        while True:
            # Merge pagination params with existing params
            request_params = {**params, "page": page, "page_size": PAGE_SIZE}

            logger.debug(f"Fetching page {page} from {endpoint}")

            response = await self._send_api_request(
                method="GET",
                endpoint=endpoint,
                params=request_params,
            )

            # Handle different response formats
            items = self._extract_items_from_response(response)

            if not items:
                logger.debug(f"No items found on page {page} for {endpoint}")
                break

            yield items

            # Check if we've reached the last page
            if len(items) < page_size:
                logger.debug(f"Last page reached for {endpoint}")
                break

            page += 1

    @staticmethod
    def _extract_items_from_response(response: Any) -> list[dict[str, Any]]:
        """
        Extract items from API response.
        
        Harbor API can return either:
        - A list directly
        - A dict with items in various keys ('items', 'data', 'results')
        
        Args:
            response: API response (list or dict)
        
        Returns:
            List of items
        """
        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            # Check common keys for items in dict responses
            return response.get("items", response.get("data", response.get("results", [])))
        else:
            return []

    # ==================== Resource-specific methods ====================

    async def get_projects(
        self,
        params: Optional[dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch projects from Harbor.
        
        Args:
            params: Optional query parameters (e.g., {'public': 'true'})
            page_size: Number of items per page
        
        Yields:
            Batches of project dictionaries
        """
        logger.info("Fetching projects from Harbor")
        async for batch in self.get_paginated_resources(
            endpoint="/projects",
            params=params,
            page_size=page_size,
        ):
            logger.debug(f"Fetched {len(batch)} projects")
            yield batch

    async def get_repositories(
        self,
        params: Optional[dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch repositories from Harbor.
        
        Args:
            params: Optional query parameters
            page_size: Number of items per page
        
        Yields:
            Batches of repository dictionaries
        """
        logger.info("Fetching repositories from Harbor")
        async for batch in self.get_paginated_resources(
            endpoint="/repositories",
            params=params,
            page_size=page_size,
        ):
            logger.debug(f"Fetched {len(batch)} repositories")
            yield batch

    async def get_artifacts_for_repository(
        self,
        project_name: str,
        repository_name: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch artifacts for a specific repository.
        
        Args:
            project_name: Name of the project
            repository_name: Name of the repository (without project prefix)
            params: Optional query parameters
            page_size: Number of items per page
        
        Yields:
            Batches of artifact dictionaries
        """
        endpoint = f"/projects/{project_name}/repositories/{repository_name}/artifacts"
        
        logger.debug(f"Fetching artifacts for {project_name}/{repository_name}")
        
        async for batch in self.get_paginated_resources(
            endpoint=endpoint,
            params=params,
            page_size=page_size,
        ):
            logger.debug(f"Fetched {len(batch)} artifacts")
            yield batch

    async def get_single_artifact(
        self,
        project_name: str,
        repository_name: str,
        reference: str,
    ) -> Optional[dict[str, Any]]:
        """
        Fetch a single artifact from Harbor API.
        
        Args:
            project_name: Name of the project (e.g., "opensource")
            repository_name: Name of the repository (e.g., "nginx")
            reference: Artifact reference - either a tag name or digest
                      (e.g., "latest" or "sha256:460a7081...")
        
        Returns:
            Artifact data as a dictionary, or None if not found
        """
        endpoint = (
            f"/projects/{project_name}/repositories/{repository_name}"
            f"/artifacts/{reference}"
        )
        
        logger.debug(
            f"Fetching artifact: {project_name}/{repository_name}:{reference}"
        )
        
        try:
            artifact = await self._send_api_request(
                method="GET",
                endpoint=endpoint,
            )
            
            logger.debug(f"Successfully fetched artifact: {artifact.get('digest')}")
            return artifact
            
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"Artifact not found: {project_name}/{repository_name}/{reference}"
                )
                return None
            # Re-raise other HTTP errors
            raise
            
        except Exception as e:
            logger.error(
                f"Failed to fetch artifact {project_name}/{repository_name}/{reference}: {str(e)}"
            )
            raise

    async def get_users(
        self,
        params: Optional[dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch users from Harbor.
        
        Args:
            params: Optional query parameters
            page_size: Number of items per page
        
        Yields:
            Batches of user dictionaries
        """
        logger.info("Fetching users from Harbor")
        async for batch in self.get_paginated_resources(
            endpoint="/users",
            params=params,
            page_size=page_size,
        ):
            logger.debug(f"Fetched {len(batch)} users")
            yield batch

