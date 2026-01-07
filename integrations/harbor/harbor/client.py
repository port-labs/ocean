"""Harbor API client for interacting with Harbor Registry."""

import asyncio
from typing import Any, AsyncGenerator, Optional

from httpx import AsyncClient, BasicAuth, HTTPStatusError, RequestError, Timeout
from loguru import logger

MAX_CONCURRENT_REQUESTS = 10
PAGE_SIZE = 50
DEFAULT_TIMEOUT = 30


class HarborClient:
    """
    Client for interacting with the Harbor Registry API.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
        api_version: str = "v2.0",
    ) -> None:
        """
        Initialize the Harbor client.
        """
        if not base_url:
            raise ValueError(
                "Harbor base_url is required but was not provided. "
                "Please set the 'baseUrl' configuration in your integration config."
            )
        if not username:
            raise ValueError(
                "Username is required for Harbor API authentication."
            )
        if not password:
            raise ValueError(
                "Password is required for Harbor API authentication."
            )
        
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version.strip("/")
        self.verify_ssl = verify_ssl
        
        # Create our own client instance so we can control SSL verification
        self.client = AsyncClient(
            timeout=Timeout(DEFAULT_TIMEOUT),
            verify=verify_ssl,
        )
        
        self._configure_authentication(username, password)
        
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def _configure_authentication(
        self, 
        username: str, 
        password: str
    ) -> None:
        """
        Configure client authentication with Basic Auth.
        """
        self._auth = BasicAuth(username, password)
        logger.info(f"Harbor client configured with Basic Auth - username: {username}")

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
        """
        if endpoint.startswith("http"):
            url = endpoint
        else:
            endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
            url = f"{self.base_url}/api/{self.api_version}{endpoint}"

        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=headers,
                    auth=self._auth,
                )
                response.raise_for_status()
                return response.json()

        except HTTPStatusError as e:
            if e.response.status_code == 429:

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
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch paginated data from the Harbor API.
        """
        if params is None:
            params = {}

        page = 1
        while True:
            request_params = {**params, "page": page, "page_size": PAGE_SIZE}

            logger.debug(f"Fetching page {page} from {endpoint}")

            response = await self._send_api_request(
                method="GET",
                endpoint=endpoint,
                params=request_params,
            )

            items = self._extract_items_from_response(response)

            if not items:
                logger.debug(f"No items found on page {page} for {endpoint}")
                break

            yield items

            if len(items) < PAGE_SIZE:
                logger.debug(f"Last page reached for {endpoint}")
                break

            page += 1

    @staticmethod
    def _extract_items_from_response(response: Any) -> list[dict[str, Any]]:
        """
        Extract items from API response.
        """
        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            # Check common keys for items in dict responses
            items = response.get("items") or response.get("data") or response.get("results")
            if isinstance(items, list):
                return items
            return []
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
        """
        logger.info("Fetching projects from Harbor")
        async for batch in self.get_paginated_resources(
            endpoint="/projects",
            params=params,
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
        """
        logger.info("Fetching repositories from Harbor")
        async for batch in self.get_paginated_resources(
            endpoint="/repositories",
            params=params,
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
        """
        endpoint = f"/projects/{project_name}/repositories/{repository_name}/artifacts"
        
        logger.debug(f"Fetching artifacts for {project_name}/{repository_name}")
        
        async for batch in self.get_paginated_resources(
            endpoint=endpoint,
            params=params,
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
        """
        logger.info("Fetching users from Harbor")
        async for batch in self.get_paginated_resources(
            endpoint="/users",
            params=params,
        ):
            logger.debug(f"Fetched {len(batch)} users")
            yield batch

