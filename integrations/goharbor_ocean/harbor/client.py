"""
Core client module for interacting with GoHarbor's API

Currently:
 - Supports Harbor v2.11.0 API
 - Handles authentication, pagination, rate limiting, and error handling

Maintainer: @50-Course (github.com/50-Course)
Created: 2025-10-12
"""

import asyncio
from typing import Any, Optional, AsyncGenerator
from urllib.parse import quote

from loguru import logger
from httpx import HTTPStatusError, Timeout

from port_ocean.utils import http_async_client

from harbor.exceptions import (
    HarborAPIError,
    InvalidConfigurationError,
    MissingCredentialsError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from harbor.utils.auth import generate_basic_auth_header
from harbor.utils.constants import (
    API_VERSION,
    DEFAULT_PAGE_SIZE,
    DEFAULT_TIMEOUT,
    MAX_CONCURRENT_REQUESTS,
    ENDPOINTS,
    HarborKind,
    ARTIFACT_QUERY_PARAMS,
)


class HarborClient:
    """
    Async HTTP client for Harbor API

    Provides methods for fetching projects, users, repositories, and artifacts
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
    ):
        """
        Initalizes Harbor API client

        Args:
            base_url: Harbor instance base URL (e.g., https://harbor.example.com)
            username: Harbor username (robot account or user)
            password: Harbor password/token
            verify_ssl: Whether to verify SSL certificates

        Raises:
            InvalidConfigurationError: If base_url is empty
            MissingCredentialsError: If username or password is missing
        """

        if not base_url or not base_url.strip():
            raise InvalidConfigurationError("base_url cannot be empty")

        if not username or username is None:
            raise MissingCredentialsError("username is required")

        if not password or password is None:
            raise MissingCredentialsError("password is required")

        base_url_clean = base_url.rstrip('/')
        api_suffix = f"/api/{API_VERSION}"
        if base_url_clean.endswith(api_suffix):
            self.base_url = base_url_clean
        else:
            self.base_url = f"{base_url_clean}{api_suffix}"
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

        self.client, self.client.timeout = http_async_client, Timeout(DEFAULT_TIMEOUT)

        auth_header_name, auth_header_value = generate_basic_auth_header(
            username, password
        )

        self.auth_headers = {auth_header_name: auth_header_value}

        # to help us control batch requests
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        logger.info(
            f"harbor_ocean::client::Initialized client for {self.base_url} "
            f"(verify_ssl={self.verify_ssl})"
        )

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Send HTTP request to Harbor API

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON request body

        Returns:
            Parsed JSON response

        Raises:
            UnauthorizedError: 401 authentication failed
            ForbiddenError: 403 permission denied
            NotFoundError: 404 resource not found
            RateLimitError: 429 rate limit exceeded
            ServerError: 5xx server error
        """
        url = (
            f"{self.base_url}{endpoint}"
            if endpoint.startswith("/")
            else f"{self.base_url}/{endpoint}"
        )

        try:
            async with self._semaphore:
                logger.debug(f"harbor_ocean::client::{method} {url} with params={params}")

                request_headers = self.auth_headers.copy()

                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=request_headers,
                )

                response.raise_for_status()
                return response.json()

        except HTTPStatusError as e:
            status_code = e.response.status_code

            match status_code:
                case 401:
                    logger.error(f"harbor_ocean::client::Authentication failed for {url}")
                    raise UnauthorizedError(
                        "Authentication failed. Check your Harbor credentials"
                    ) from e

                case 403:
                    logger.error(f"harbor_ocean::client::Permission denied for {url}")
                    raise ForbiddenError(
                        "Permission denied. Check your Harbor user permissions"
                    ) from e

                case 404:
                    resource = endpoint.split("/")[-1] if "/" in endpoint else endpoint
                    logger.warning(f"harbor_ocean::client::Resource not found: {url}")
                    raise NotFoundError(resource) from e

                case 429:
                    # we're been throttled - retry after specified time
                    retry_after = int(e.response.headers.get("Retry-After", "60"))
                    logger.warning(
                        f"harbor_ocean::client::Rate limited. Retrying after {retry_after} seconds"
                    )

                    await asyncio.sleep(retry_after)
                    return await self._send_api_request(
                        method, endpoint, params, json_data
                    )

                case _ if status_code >= 500:
                    logger.error(f"harbor_ocean::client::Harbor server error ({status_code}) for {url}")
                    raise ServerError(
                        f"Harbor server error: {status_code}", status_code
                    ) from e

                case _:
                    logger.error(f"harbor_ocean::client::Harbor API error ({status_code}) for {url}")
                    raise HarborAPIError(f"API error: {status_code}", status_code)

    def _build_endpoint_url(
        self,
        kind: HarborKind,
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
    ):
        """
        Constructs the API endpoint URL based on resource kind and parameters

        Raises:
          InvalidConfigurationError: If required parameters are missing
        """
        match kind:
            case HarborKind.PROJECT:
                return ENDPOINTS["projects"]

            case HarborKind.USER:
                return ENDPOINTS["users"]

            case HarborKind.REPOSITORY:
                if not project_name:
                    raise InvalidConfigurationError(
                        "project_name is required when fetching repositories"
                    )

                encoded_project = quote(project_name, safe="")
                return ENDPOINTS["repositories"].format(project_name=encoded_project)

            case HarborKind.ARTIFACT:
                if not project_name or not repository_name:
                    raise InvalidConfigurationError(
                        "Both project_name and repository_name are required when fetching artifacts"
                    )
                # double-encode repository name
                # First encoding: library/nginx -> library%2Fnginx
                # Second encoding: library%2Fnginx -> library%252Fnginx
                encoded_project = quote(project_name, safe="")
                encoded_repo = quote(quote(repository_name, safe=""), safe="")

                return ENDPOINTS["artifacts"].format(
                    project_name=encoded_project, repository_name=encoded_repo
                )

    async def get_paginated_resources(
        self,
        kind: HarborKind,
        project_name: Optional[str] = None,
        repository_name: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Pagination router that fetches paginated resources from GoHarbor API

        Usage:
            async for projects in client.get_paginated_resources(HarborKind.PROJECT):
                for project in projects:
                    print(project['name'])

        Args:
            kind: Resource type to fetch
            project_name: Project name (required for repositories and artifacts)
            repository_name: Repository name (required for artifacts)
            params: Additional query parameters (filters, enrichment flags, etc.)

        Yields:
            Batches of resources as lists of dictionaries
        """
        endpoint = self._build_endpoint_url(kind, project_name, repository_name)

        query_params = params.copy() if params else {}
        if 'page_size' not in query_params:
            query_params['page_size'] = DEFAULT_PAGE_SIZE

        if kind == HarborKind.ARTIFACT:
            for key, val in ARTIFACT_QUERY_PARAMS.items():
                if key not in query_params:
                    query_params[key] = val

        page = 1
        total_fetched = 0

        logger.info(
            f'harbor_ocean::client::Starting paginated fetch for {kind} '
                f'(project={project_name}, repo={repository_name})'
        )

        while True:
            query_params['page'] = page

            try:
                response_data = await self._send_api_request(
                    "GET",
                    endpoint,
                    params=query_params
                )

                items = response_data if isinstance(response_data, list) else []

                if not items:
                    logger.info(
                        f"harbor_ocean::client::Completed pagination for {kind}. "
                        f"Total fetched: {total_fetched}"
                    )
                    break

                total_fetched += len(items)
                logger.debug(
                    f"harbor_ocean::client::Fetched page {page} for {kind}: {len(items)} items "
                    f"(total so far: {total_fetched})"
                )

                yield items
                page += 1

            except Exception as e:
                logger.error(f"harbor_ocean::client::Error fetching {kind} page {page}: {e}")
                raise


    async def get_paginated_projects(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Convenience method to fetch projects

        Args:
            params: Optional filters (public, private, name, etc.)

        Yields:
            Batches of projects
        """
        async for batch in self.get_paginated_resources(
            HarborKind.PROJECT, params=params
        ):
            yield batch

    async def get_paginated_users(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Method to fetch users

        Args:
            params: Optional filters

        Yields:
            Batches of users
        """
        async for batch in self.get_paginated_resources(HarborKind.USER, params=params):
            yield batch

    async def get_paginated_repositories(
        self,
        project_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Method to fetch repositories for a project

        Args:
            project_name: Project name
            params: Optional filters

        Yields:
            Batches of repositories
        """
        async for batch in self.get_paginated_resources(
            HarborKind.REPOSITORY, project_name=project_name, params=params
        ):
            yield batch

    async def get_paginated_artifacts(
        self,
        project_name: str,
        repository_name: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Method to fetch artifacts for a repository

        Args:
            project_name: Project name
            repository_name: Repository name
            params: Optional filters (with_tag, with_scan_overview, etc.)

        Yields:
            Batches of artifacts
        """
        async for batch in self.get_paginated_resources(
            HarborKind.ARTIFACT,
            project_name=project_name,
            repository_name=repository_name,
            params=params,
        ):
            yield batch
