import asyncio
import functools
import re
from typing import Any, AsyncGenerator, Dict, Optional, cast

import httpx
from aiolimiter import AsyncLimiter
from httpx import BasicAuth
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from port_ocean.utils.cache import cache_iterator_result

# Rate limit docs: https://support.atlassian.com/bitbucket-cloud/docs/api-request-limits/
DEFAULT_BITBUCKET_RATE_LIMIT = 1000  # requests per hour
DEFAULT_BITBUCKET_RATE_LIMIT_WINDOW = 3600  # 1 hour
DEFAULT_PAGE_SIZE = 25  # items per page
DEFAULT_MAX_CONCURRENT_REQUESTS = 10  # concurrent repository PR requests


class BitbucketClient:
    """
    A client for interacting with the Bitbucket Server API.
    Handles authentication, rate limiting, and provides methods for accessing various Bitbucket resources.
    """

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str,
        webhook_secret: str | None = None,
        app_host: str | None = None,
        is_version_8_7_or_older: bool = False,
        rate_limit: int = DEFAULT_BITBUCKET_RATE_LIMIT,
        rate_limit_window: int = DEFAULT_BITBUCKET_RATE_LIMIT_WINDOW,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_concurrent_requests: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        projects_filter_regex: str | None = None,
        projects_filter_suffix: str | None = None,
    ):
        """
        Initialize the Bitbucket client with authentication and configuration.

        Args:
            username: Bitbucket username for authentication
            password: Bitbucket password/token for authentication
            base_url: Base URL of the Bitbucket server
            webhook_secret: Optional secret for webhook signature verification
            app_host: Optional host URL for webhook callbacks
            is_version_8_7_or_older: Whether the Bitbucket Server version is 8.7 or older
            rate_limit: Maximum number of requests allowed within the rate limit window
            rate_limit_window: Time window in seconds for rate limiting (default: 3600 = 1 hour)
            page_size: Number of items per page for paginated requests (default: 25)
            max_concurrent_requests: Maximum number of concurrent repository PR requests (default: 10)
            projects_filter_regex: Optional regex pattern to filter project keys (e.g., "^PROJ-.*")
            projects_filter_suffix: Optional suffix pattern to filter project keys (e.g., "-PROD")
        """
        self.username = username
        self.password = password
        self.base_url = base_url
        self.bitbucket_auth = BasicAuth(username=username, password=password)
        self.client = http_async_client
        self.client.auth = self.bitbucket_auth
        self.client.timeout = httpx.Timeout(60)
        self.app_host = app_host
        self.webhook_secret = webhook_secret
        self.is_version_8_7_or_older = is_version_8_7_or_older
        self.page_size = page_size
        self.max_concurrent_requests = max_concurrent_requests

        self.projects_filter_regex = (
            re.compile(projects_filter_regex) if projects_filter_regex else None
        )
        self.projects_filter_suffix = projects_filter_suffix

        # Despite this, being the rate limits, we do not reduce to the lowest common factor because we want to allow as much
        # concurrency as possible. This is because we expect most users to have resources
        # synced under one hour.
        self.rate_limiter = AsyncLimiter(rate_limit, rate_limit_window)

        # Initialize semaphore for controlling concurrent PR requests
        self.pr_semaphore = asyncio.BoundedSemaphore(max_concurrent_requests)

    async def _send_api_request(
        self,
        method: str,
        path: str,
        payload: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any] | None:
        """
        Send an HTTP request to the Bitbucket API with rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            payload: Optional request payload

        Returns:
            JSON response from the API or None if the resource is not found (404)
        """
        url = f"{self.base_url}/rest/api/1.0/{path}"
        async with self.rate_limiter:
            try:
                logger.info(
                    f"Sending {method} request to {url} with payload: {payload}"
                )
                response = await self.client.request(
                    method, url, params=params, json=payload
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                if e.response.status_code == 404:
                    return None
                raise
            except httpx.HTTPError as e:
                logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
                raise

    def _should_include_project(self, project_key: str) -> bool:
        """
        Check if a project should be included based on filter patterns.

        Args:
            project_key: The project key to check

        Returns:
            True if the project should be included, False otherwise
        """
        # If no filters are set, include all projects
        if not self.projects_filter_regex and not self.projects_filter_suffix:
            return True

        # Check regex filter
        if self.projects_filter_regex:
            if not self.projects_filter_regex.match(project_key):
                return False

        # Check suffix filter
        if self.projects_filter_suffix:
            if not project_key.endswith(self.projects_filter_suffix):
                return False

        return True

    async def get_paginated_resource(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: Optional[int] = None,
        full_response: bool = False,
    ) -> AsyncGenerator[list[Any], None]:
        """
        Fetch paginated resources from the Bitbucket API.

        Args:
            path: API endpoint path
            params: Optional query parameters
            page_size: Number of items per page
            full_response: Whether to return full response or just values

        Yields:
            Batches of resource items
        """
        params = params or {}
        effective_page_size = page_size if page_size is not None else self.page_size
        params["limit"] = effective_page_size
        start = 0

        while True:
            params["start"] = start
            try:
                data = await self._send_api_request("GET", path, params=params)
                if not data:
                    break
                values: list[dict[str, Any]] = data.get("values", [])
                if not values:
                    break

                if full_response:
                    yield [data]
                else:
                    yield values
                if next_page := data.get("nextPageStart"):
                    start = next_page
                if data.get("isLastPage") or not next_page:
                    break
            except httpx.HTTPError as e:
                logger.error(f"Error fetching paginated resource: {e}")
                break

    async def _get_all_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Internal method to fetch all projects from Bitbucket.

        Yields:
            Batches of project data
        """
        async for project_batch in self.get_paginated_resource("projects"):
            yield cast(list[dict[str, Any]], project_batch)

    async def _get_projects_with_filter(
        self, projects_filter: set[str]
    ) -> list[dict[str, Any]]:
        """
        Internal method to fetch specific projects by their keys.

        Args:
            projects_filter: Set of project keys to fetch

        Returns:
            List of filtered project data
        """
        projects = dict[str, dict[str, Any]]()
        async for project_batch in self.get_projects():
            logger.info(f"Received project batch: {project_batch}")
            filtered_projects = filter(
                lambda project: project["key"] in projects_filter, project_batch
            )
            projects.update({project["key"]: project for project in filtered_projects})
            if len(projects) == len(projects_filter):
                break
        return list(projects.values())

    @cache_iterator_result()
    async def get_projects(
        self, projects_filter: Optional[set[str]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get projects from Bitbucket, optionally filtered by project keys.
        Also applies regex/suffix filters if configured.

        Args:
            projects_filter: Optional set of project keys to filter by

        Yields:
            Batches of project data
        """
        logger.info(
            f"Getting projects with filter: {projects_filter}, "
            f"regex: {self.projects_filter_regex}, suffix: {self.projects_filter_suffix}"
        )
        if projects_filter:
            filtered_projects = await self._get_projects_with_filter(projects_filter)
            # Apply regex/suffix filters
            final_projects = [
                p for p in filtered_projects if self._should_include_project(p["key"])
            ]
            if final_projects:
                yield final_projects
        else:
            async for project_batch in self._get_all_projects():
                # Apply regex/suffix filters to each batch
                filtered_batch = [
                    p for p in project_batch if self._should_include_project(p["key"])
                ]
                if filtered_batch:
                    yield filtered_batch

    async def get_repositories_for_project(
        self, project_key: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all repositories for a specific project.

        Args:
            project_key: Key of the project

        Yields:
            Batches of repository data
        """
        async for repo_batch in self.get_paginated_resource(
            f"projects/{project_key}/repos"
        ):
            yield repo_batch

    @cache_iterator_result()
    async def get_repositories(
        self, projects_filter: set[str] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get repositories across multiple projects, optionally filtered by project keys.

        Args:
            projects_filter: Optional set of project keys to filter by

        Yields:
            Batches of repository data
        """
        tasks = []
        async for project_batch in self.get_projects(projects_filter):
            for project in project_batch:
                tasks.append(self.get_repositories_for_project(project["key"]))

        async for repo_batch in stream_async_iterators_tasks(*tasks):
            yield repo_batch

    async def _get_pull_requests_for_repository(
        self, project_key: str, repo_slug: str, state: str = "OPEN"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Internal method to get pull requests for a specific repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository
            state: State of pull requests to fetch (default: "OPEN")

        Yields:
            Batches of pull request data
        """
        params = {"state": state}
        async for pr_batch in self.get_paginated_resource(
            f"projects/{project_key}/repos/{repo_slug}/pull-requests",
            params=params,
        ):
            yield cast(list[dict[str, Any]], pr_batch)

    @cache_iterator_result()
    async def get_pull_requests(
        self, projects_filter: set[str] | None = None, state: str = "OPEN"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get pull requests across multiple repositories, optionally filtered by project keys.
        Uses semaphore to control concurrency for parallel PR fetching.

        Args:
            projects_filter: Optional set of project keys to filter by
            state: State of pull requests to fetch (default: "OPEN")

        Yields:
            Batches of pull request data
        """
        tasks = []
        async for repo_batch in self.get_repositories(projects_filter):
            for repo in repo_batch:
                # Wrap each repository PR fetcher with semaphore for controlled concurrency
                # Use functools.partial to properly bind repository and state parameters
                pr_iterator_func = functools.partial(
                    self._get_pull_requests_for_repository,
                    repo["project"]["key"],
                    repo["slug"],
                    state,
                )
                tasks.append(
                    semaphore_async_iterator(self.pr_semaphore, pr_iterator_func)
                )

        async for pr_batch in stream_async_iterators_tasks(*tasks):
            yield pr_batch

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all users from Bitbucket.

        Yields:
            Batches of user data
        """
        async for user_batch in self.get_paginated_resource("users"):
            yield cast(list[dict[str, Any]], user_batch)

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        """
        Get a single project by its key.

        Args:
            project_key: Key of the project

        Returns:
            Project data or empty dict if not found
        """
        project = await self._send_api_request("GET", f"projects/{project_key}")
        return project or {}

    async def get_single_repository(
        self, project_key: str, repo_slug: str
    ) -> dict[str, Any]:
        """
        Get a single repository by project key and repository slug.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            Repository data or empty dict if not found
        """
        repository = await self._send_api_request(
            "GET", f"projects/{project_key}/repos/{repo_slug}"
        )
        if not repository:
            return {}

        return repository

    async def get_single_pull_request(
        self, project_key: str, repo_slug: str, pr_key: str
    ) -> dict[str, Any]:
        """
        Get a single pull request by project key, repository slug, and PR key.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository
            pr_key: Key of the pull request

        Returns:
            Pull request data or empty dict if not found
        """
        pull_request = await self._send_api_request(
            "GET",
            f"projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_key}",
        )
        return pull_request or {}

    async def get_single_user(self, user_key: str) -> dict[str, Any]:
        """
        Get a single user by their key.

        Args:
            user_key: Key of the user

        Returns:
            User data or empty dict if not found
        """
        user = await self._send_api_request("GET", f"users/{user_key}")
        return user or {}

    async def _get_application_properties(self) -> dict[str, Any]:
        """
        Internal method to get Bitbucket application properties.

        Returns:
            Application properties data or empty dict if not found
        """
        return (
            await self._send_api_request(
                method="GET",
                path="application-properties",
            )
            or {}
        )

    async def healthcheck(self) -> None:
        """
        Perform a health check of the Bitbucket connection.

        Raises:
            Exception: If connection to Bitbucket fails
        """
        try:
            await self._get_application_properties()
            logger.info("Successfully connected to Bitbucket Server")
        except Exception as e:
            logger.error(f"Failed to connect to Bitbucket Server: {e}")
            raise ConnectionError("Failed to connect to Bitbucket Server") from e
