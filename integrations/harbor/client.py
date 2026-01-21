import asyncio
from typing import Any, AsyncGenerator
from aiolimiter import AsyncLimiter

import httpx
from httpx import BasicAuth, Timeout, HTTPStatusError
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils import http_async_client
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result

from constants import *


class HarborClient:
    """Client for interacting with Harbor API."""

    def __init__(
            self,
            harbor_url: str,
            username: str,
            password: str,
            http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize Harbor client.

        Args:
            harbor_url: Base URL of Harbor instance (e.g., http://localhost:8081)
            username: Harbor username (admin or robot account)
            password: Harbor password or robot token
        """
        self.harbor_url = harbor_url.rstrip("/")
        self.api_url = f"{self.harbor_url}/api/v2.0"
        self.username = username
        self.password = password

        # Configure HTTP client
        self.client = http_async_client if not http_client else http_client
        self.client.timeout = Timeout(CLIENT_TIMEOUT)

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self.rate_limiter = AsyncLimiter(1000, 3600)

        logger.info(f"Initialized Harbor client for {self.harbor_url}")

    async def _get_csrf_token(self) -> str:
        """Fetch CSRF token from Harbor."""
        try:
            response = await self.client.get(
                f"{self.api_url}/systeminfo",
                auth=BasicAuth(self.username, self.password),
            )
            response.raise_for_status()
            # CSRF token is in the response headers
            return response.headers.get("X-Harbor-CSRF-Token", "")
        except Exception as e:
            logger.warning(f"Failed to fetch CSRF token: {e}")
            return ""

    async def _send_api_request(
            self,
            endpoint: str,
            method: str = "GET",
            params: dict[str, Any] | None = None,
            json_data: dict[str, Any] | None = None,
    ) -> tuple[Any, dict[str, str]]:
        """
        Send a request to the Harbor API.

        Args:
            endpoint: API endpoint path (e.g., "/projects")
            method: HTTP method (GET, POST, DELETE, etc.)
            params: Query parameters
            json_data: JSON body for POST/PUT requests

        Returns:
            Tuple of (response JSON or empty dict, response headers)
        """
        url = f"{self.api_url}{endpoint}"

        try:
            async with self.rate_limiter, self._semaphore:
                logger.debug(f"Sending {method} request to {url} with params: {params}")
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                if method in ["POST", "PUT", "DELETE", "PATCH"]:
                    csrf_token = await self._get_csrf_token()
                    if csrf_token:
                        headers["X-Harbor-CSRF-Token"] = csrf_token

                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    auth=BasicAuth(self.username, self.password),
                    headers=headers,
                    json=json_data,
                )

                response.raise_for_status()

                logger.debug(
                    f"Request to {url} completed with status {response.status_code} "
                )

                try:
                    headers_dict = (
                        dict(response.headers)
                        if hasattr(response.headers, "__iter__")
                        else {}
                    )
                except (TypeError, AttributeError):
                    headers_dict = {}

                payload = response.json() if response.text else {}

                return payload, headers_dict
        except HTTPStatusError as e:
            logger.error(
                f"HTTP error for {method} {url}: "
                f"Status {e.response.status_code}, Response: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {method} {url}: {str(e)}")
            raise

    async def _get_paginated_data(
            self,
            endpoint: str,
            params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch paginated data from Harbor API.

        Harbor uses page-based pagination with X-Total-Count header.

        Args:
            endpoint: API endpoint path
            params: Additional query parameters

        Yields:
            Batches of items from the API
        """
        if params is None:
            params = {}

        page = 1
        params["page_size"] = PAGE_SIZE

        while True:
            params["page"] = page

            logger.debug(f"Fetching page {page} from {endpoint}")

            data, headers = await self._send_api_request(
                endpoint=endpoint, params=params
            )

            if not data:
                logger.debug(f"No more data at page {page} for {endpoint}")
                break

            total_count = headers.get("X-Total-Count", "unknown")
            logger.info(
                f"Received {len(data)} items from {endpoint} "
                f"(page {page}, total: {total_count})"
            )

            yield data

            # If we received fewer items than page size, we've reached the end
            if len(data) < PAGE_SIZE:
                break

            page += 1

    @cache_iterator_result()
    async def get_paginated_projects(
            self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all projects with pagination.

        Args:
            params: Query parameters (name, public, etc.)

        Yields:
            Batches of project data
        """
        logger.info("Fetching projects from Harbor")

        if params is None:
            params = {}

        # Ensure we get detailed project information
        params["with_detail"] = True

        async for projects in self._get_paginated_data("/projects", params):
            yield projects

    async def get_project(self, project_name_or_id: str | int) -> dict[str, Any]:
        """
        Get a single project by name or ID.

        Args:
            project_name_or_id: Project name or ID

        Returns:
            Project data
        """
        logger.info(f"Fetching project: {project_name_or_id}")

        data, _ = await self._send_api_request(
            endpoint=f"/projects/{project_name_or_id}"
        )

        return data

    async def get_paginated_users(
            self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all users with pagination.

        Args:
            params: Query parameters (q for filtering)

        Yields:
            Batches of user data
        """
        logger.info("Fetching users from Harbor")

        async for users in self._get_paginated_data("/users", params):
            yield users

    async def get_user(self, user_id: int) -> dict[str, Any]:
        """
        Get a single user by ID.

        Args:
            user_id: User ID

        Returns:
            User data
        """
        logger.info(f"Fetching user: {user_id}")

        data, _ = await self._send_api_request(endpoint=f"/users/{user_id}")

        return data

    @cache_iterator_result()
    async def get_paginated_repositories(
            self, project_name: str | None = None, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get repositories with pagination.

        Args:
            project_name: Optional project name to filter repositories
            params: Query parameters (q for filtering, sort, etc.)

        Yields:
            Batches of repository data
        """
        if project_name:
            endpoint = f"/projects/{project_name}/repositories"
            logger.info(f"Fetching repositories for project: {project_name}")
        else:
            endpoint = "/repositories"
            logger.info("Fetching all repositories")

        async for repositories in self._get_paginated_data(endpoint, params):
            yield repositories

    async def get_repository(
            self, project_name: str, repository_name: str
    ) -> dict[str, Any]:
        """
        Get a single repository.

        Args:
            project_name: Project name
            repository_name: Repository name

        Returns:
            Repository data
        """
        logger.info(f"Fetching repository: {project_name}/{repository_name}")

        data, _ = await self._send_api_request(
            endpoint=f"/projects/{project_name}/repositories/{repository_name}"
        )

        return data

    async def get_paginated_artifacts(
            self,
            project_name: str,
            repository_name: str,
            params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get artifacts for a repository with pagination.

        Args:
            project_name: Project name
            repository_name: Repository name
            params: Query parameters (with_tag, with_scan_overview, etc.)

        Yields:
            Batches of artifact data
        """
        logger.info(f"Fetching artifacts for {project_name}/{repository_name}")

        if params is None:
            params = {}

        # Set defaults for artifact details
        params.setdefault("with_tag", True)
        params.setdefault("with_scan_overview", True)
        params.setdefault("with_label", False)

        endpoint = f"/projects/{project_name}/repositories/{repository_name}/artifacts"

        async for artifacts in self._get_paginated_data(endpoint, params):
            yield artifacts

    async def get_artifact(
            self,
            project_name: str,
            repository_name: str,
            reference: str,
            params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get a single artifact by reference (digest or tag).

        Args:
            project_name: Project name
            repository_name: Repository name
            reference: Artifact reference (digest or tag)
            params: Query parameters

        Returns:
            Artifact data
        """
        logger.info(f"Fetching artifact: {project_name}/{repository_name}@{reference}")

        data, _ = await self._send_api_request(
            endpoint=f"/projects/{project_name}/repositories/{repository_name}/artifacts/{reference}",
            params=params,
        )

        return data

    @cache_iterator_result()
    async def get_all_projects_with_repositories(
            self,
    ) -> AsyncGenerator[tuple[dict[str, Any], list[dict[str, Any]]], None]:
        """
        Get all projects with their repositories.

        Yields:
            Tuples of (project, repositories)
        """
        logger.info("Fetching all projects with repositories")

        async for projects in self.get_paginated_projects():
            for project in projects:
                project_name = project.get("name")

                if not project_name:
                    logger.warning(f"Project missing name: {project}")
                    continue

                repositories = []
                async for repo_batch in self.get_paginated_repositories(project_name):
                    repositories.extend(repo_batch)

                yield project, repositories

    async def get_all_artifacts_for_projects(
            self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all artifacts across all projects and repositories.

        Args:
            params: Query parameters for artifacts

        Yields:
            Batches of artifact data
        """
        logger.info("Fetching all artifacts across all projects")

        async for projects in self.get_paginated_projects():
            for project in projects:
                project_name = project.get("name")

                if not project_name:
                    continue

                async for repositories in self.get_paginated_repositories(project_name):
                    # Get artifacts for each repository in parallel
                    tasks = []

                    for repo in repositories:
                        # Extract repository name (format: "project/repo")
                        repo_full_name = repo.get("name", "")

                        if "/" in repo_full_name:
                            repo_name = repo_full_name.split("/", 1)[1]
                        else:
                            repo_name = repo_full_name

                        if not repo_name:
                            continue

                        tasks.append(
                            self.get_paginated_artifacts(
                                project_name, repo_name, params
                            )
                        )

                    # Stream artifacts from all repositories in parallel
                    if tasks:
                        async for artifact_batch in stream_async_iterators_tasks(
                                *tasks
                        ):
                            yield artifact_batch

    async def get_webhooks(self, project_name: str) -> list[dict[str, Any]]:
        """
        Get webhooks for a project.

        Args:
            project_name: Project name

        Returns:
            List of webhook configurations
        """
        logger.info(f"Fetching webhooks for project: {project_name}")

        try:
            data, _ = await self._send_api_request(
                endpoint=f"/projects/{project_name}/webhook/policies"
            )
            return data
        except Exception as e:
            logger.error(f"Failed to fetch webhooks for {project_name}: {e}")
            return []

    async def create_webhook(
            self,
            project_name: str,
            webhook_url: str,
            event_types: list[str],
            name: str | None = None,
            auth_header: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Create a webhook for a project.

        Args:
            project_name: Project name
            webhook_url: URL to send webhook events to
            event_types: List of event types to trigger webhook
            name: Optional webhook name
            auth_header: Optional authorization header value

        Returns:
            Created webhook data or None if failed
        """
        if name is None:
            name = f"Port Ocean Webhook - {project_name}"

        logger.info(f"Creating webhook for project {project_name} to {webhook_url}")

        webhook_config = {
            "name": name,
            "enabled": True,
            "event_types": event_types,
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "skip_cert_verify": True,
                    "payload_format": "CloudEvents",
                }
            ],
        }

        # Add auth header if provided
        if auth_header:
            webhook_config["targets"][0]["auth_header"] = auth_header

        try:
            data, header = await self._send_api_request(
                endpoint=f"/projects/{project_name}/webhook/policies",
                method="POST",
                json_data=webhook_config,
            )
            location = header.get("location", "")
            return location.split("/")[-1] if location else None
        except Exception as e:
            logger.error(f"Failed to create webhook for {project_name}: {e}")
            return None

    async def setup_webhooks_for_all_projects(
            self,
            webhook_url: str,
            event_types: list[str] | None = None,
            auth_header: str | None = None,
    ) -> dict[str, Any]:
        """
        Set up webhooks for all projects.

        Args:
            webhook_url: URL to send webhook events to
            event_types: List of event types (defaults to all artifact events)
            auth_header: Optional authorization header

        Returns:
            Dictionary with success/failure counts
        """
        if event_types is None:
            event_types = EVENT_TYPES

        logger.info(f"Setting up webhooks for all projects to {webhook_url}")

        results = {
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "projects": [],
        }

        # Fetch all projects
        async for projects in self.get_paginated_projects():
            for project in projects:
                project_name = project.get("name")

                if not project_name:
                    continue

                # Check if webhook already exists
                existing_webhooks = await self.get_webhooks(project_name)
                webhook_exists = any(
                    wh.get("targets", [{}])[0].get("address") == webhook_url
                    for wh in existing_webhooks
                )

                if webhook_exists:
                    logger.info(f"Webhook already exists for project {project_name}")
                    results["skipped"] += 1
                    continue

                # Create webhook
                webhook = await self.create_webhook(
                    project_name=project_name,
                    webhook_url=webhook_url,
                    event_types=event_types,
                    auth_header=auth_header,
                )

                if webhook:
                    results["success"] += 1
                    results["projects"].append(project_name)
                else:
                    results["failed"] += 1

        logger.info(
            f"Webhook setup complete: "
            f"{results['success']} created, "
            f"{results['skipped']} skipped, "
            f"{results['failed']} failed"
        )

        return results
