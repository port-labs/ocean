"""Harbor API Client.

This module provides the HTTP client for interacting with the Harbor API.
It handles authentication, pagination, rate limiting, and webhook management.
"""

import asyncio
from typing import Any, AsyncGenerator, Optional
from loguru import logger
from httpx import BasicAuth, HTTPStatusError, Timeout

from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean
from ..constants import DEFAULT_PAGE_SIZE, WEBHOOK_EVENTS, CLIENT_TIMEOUT, MAX_CONCURRENT_REQUESTS


class HarborClient:
    """Client for interacting with the Harbor API.

    This client provides methods for fetching Harbor resources including
    projects, users, repositories, and artifacts. It handles authentication,
    pagination, rate limiting, error handling, and webhook management.

    Uses Ocean's http_async_client for optimal performance and integration
    with the Ocean framework.
    """

    def __init__(
        self,
        harbor_url: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
    ):
        """Initialize the Harbor client.

        Args:
            harbor_url: Base URL of the Harbor instance (e.g., https://harbor.example.com)
            username: Harbor username for authentication
            password: Harbor password for authentication
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        self.harbor_url = harbor_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self._client = http_async_client

        # Configure Ocean's HTTP client with Basic Auth
        self.client = http_async_client
        self.client.auth = BasicAuth(username, password)
        self.client.timeout = Timeout(CLIENT_TIMEOUT)

        # Semaphore for controlling concurrent requests
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        logger.info(f"Initialized Harbor client for {self.harbor_url}")

    async def validate_connection(self) -> bool:
        """Validate the connection to Harbor.

        Returns:
            bool: True if connection is successful

        Raises:
            Exception: If connection fails
        """
        logger.info(f"Validating connection to Harbor at {self.harbor_url}")

        try:
            response = await self._send_api_request(
                method="GET",
                endpoint="/api/v2.0/systeminfo"
            )
            logger.info(
                f"Successfully validated Harbor connection. Version: {response.get('harbor_version', 'unknown')}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to validate Harbor connection: {e}")
            raise

    async def _send_api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Send an API request with centralized error handling and rate limiting.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (e.g., "/api/v2.0/projects")
            params: Query parameters
            json: JSON body for POST/PUT requests

        Returns:
            Response JSON data

        Raises:
            HTTPStatusError: For HTTP errors
        """
        if not self._client:
            raise RuntimeError("HTTP client not initialized")

        if not endpoint.startswith('/api/'):
            endpoint = f"/api/v2.0{endpoint}"

        url = endpoint if endpoint.startswith("http") else f"{self.harbor_url}{endpoint}"


        logger.debug(
            f"Sending {method} request to {endpoint}",
            extra={
                "method": method,
                "url": url,
                "params": params,
            }
        )

        try:
            async with self._semaphore:
                import time
                start_time = time.time()

                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                )

                latency = time.time() - start_time

                response.raise_for_status()

                logger.debug(
                    f"Request successful: {method} {endpoint}",
                    extra={
                        "status_code": response.status_code,
                        "latency_ms": round(latency * 1000, 2),
                    }
                )

                return response.json() if response.content else None

        except HTTPStatusError as e:
            logger.error(
                f"HTTP error: {method} {endpoint}",
                extra={
                    "status_code": e.response.status_code,
                    "response_text": e.response.text,
                    "url": url,
                }
            )

            # Handle rate limiting with exponential backoff
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", "60"))
                logger.warning(
                    f"Rate limited. Retrying after {retry_after} seconds",
                    extra={"retry_after": retry_after}
                )
                await asyncio.sleep(retry_after)
                return await self._send_api_request(method, endpoint, params, json)

            raise
        except Exception as e:
            logger.error(
                f"Request failed: {method} {endpoint}",
                extra={"error": str(e)}
            )
            raise

    async def _get(self, endpoint: str, **kwargs) -> Any:
        """Make GET request"""
        return await self._send_api_request("GET", endpoint, **kwargs)

    async def _post(self, endpoint: str, **kwargs) -> Any:
        """POST request wrapper."""
        return await self._send_api_request("POST", endpoint, **kwargs)

    async def _put(self, endpoint: str, **kwargs) -> Any:
        """PUT request wrapper."""
        return await self._send_api_request("PUT", endpoint, **kwargs)

    async def _delete(self, endpoint: str, **kwargs) -> Any:
        """DELETE request wrapper."""
        return await self._send_api_request("DELETE", endpoint, **kwargs)


    # ========================================================================
    # Pagination Helper - DRY for all paginated endpoints
    # ========================================================================

    async def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any],
        page_size: int = 100
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Generic pagination handler for Harbor API.

        Args:
            endpoint: API endpoint to paginate
            params: Query parameters
            page_size: Items per page

        Yields:
            Lists of items from each page
        """
        page = 1
        params = params.copy()  # Don't modify original
        params["page_size"] = page_size

        while True:
            params["page"] = page
            logger.debug(f"Fetching page {page} from {endpoint}")

            try:
                items = await self._get(endpoint, params=params)

                if not items:
                    logger.debug(
                        f"No more items on page {page}, stopping pagination")
                    break

                yield items

                # Stop if we got fewer items than page_size (last page)
                if len(items) < page_size:
                    logger.debug(
                        f"Received {len(items)} items (< {page_size}), last page")
                    break

                page += 1

            except Exception as e:
                logger.error(
                    f"Error fetching page {page} from {endpoint}: {e}")
                raise

    # ========================================================================
    # Connection & Authentication
    # ========================================================================

    async def validate_connection(self) -> bool:
        """
        Validate Harbor connection and credentials.

        Returns:
            True if connection is valid

        Raises:
            Exception: If connection fails
        """
        try:
            logger.info("Validating Harbor connection")
            await self._get("/api/v2.0/systeminfo")
            logger.info("Harbor connection validated successfully")
            return True
        except Exception as e:
            logger.error(f"Harbor connection validation failed: {e}")
            raise

    async def get_current_user(self) -> dict[str, Any]:
        """Get current authenticated user information."""
        logger.debug("Fetching current user information")
        return await self._get("/users/current")

    async def has_system_admin_permission(self) -> bool:
        """Check if current user has system admin permissions."""
        try:
            user = await self.get_current_user()
            is_admin = user.get("sysadmin_flag", False)
            logger.info(
                f"User {user.get('username')} system admin status: {is_admin}"
            )
            return is_admin
        except Exception as e:
            logger.error(f"Failed to check admin permissions: {e}")
            return False

    # ========================================================================
    # Projects API
    # ========================================================================

    async def get_paginated_projects(
        self,
        params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch projects with pagination.

        Args:
            params: Query parameters (page_size, q, etc.)

        Yields:
            Lists of project dictionaries
        """
        page_size = params.get("page_size", 100)
        async for projects in self._paginate("/projects", params, page_size):
            yield projects

    async def get_project(self, project_name_or_id: str) -> Optional[dict[str, Any]]:
        """
        Get a single project by name or ID.

        Args:
            project_name_or_id: Project name or ID

        Returns:
            Project dictionary or None if not found
        """
        try:
            return await self._get(f"/projects/{project_name_or_id}")
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Project {project_name_or_id} not found")
                return None
            raise

    async def get_project_members(
        self,
        project_name_or_id: str,
        entityname: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Get project members.

        Args:
            project_name_or_id: Project name or ID
            entityname: Filter by entity name (optional)

        Returns:
            List of project members
        """
        params = {}
        if entityname:
            params["entityname"] = entityname

        try:
            return await self._get(
                f"/projects/{project_name_or_id}/members",
                params=params
            ) or []
        except Exception as e:
            logger.error(
                f"Failed to fetch members for {project_name_or_id}: {e}")
            return []

    async def has_project_admin_permission(
        self,
        project_name_or_id: str
    ) -> bool:
        """
        Check if current user has admin permissions for a project.

        Args:
            project_name_or_id: Project name or ID

        Returns:
            True if user has project admin permissions
        """
        try:
            user = await self.get_current_user()
            username = user.get("username")

            members = await self.get_project_members(project_name_or_id, username)

            for member in members:
                if member.get("entity_name") == username:
                    has_admin = member.get("role_id") == 1  # ProjectAdmin role
                    logger.info(
                        f"User {username} admin status for {project_name_or_id}: {has_admin}"
                    )
                    return has_admin

            logger.warning(
                f"User {username} is not a member of {project_name_or_id}")
            return False

        except Exception as e:
            logger.error(f"Failed to check project permissions: {e}")
            return False

    # ========================================================================
    # Users API
    # ========================================================================

    async def get_paginated_users(
        self,
        params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch users with pagination.

        Args:
            params: Query parameters (page_size, q, etc.)

        Yields:
            Lists of user dictionaries
        """
        page_size = params.get("page_size", 100)
        async for users in self._paginate("/users", params, page_size):
            yield users

    # ========================================================================
    # Repositories API
    # ========================================================================

    async def get_all_repositories(
        self,
        params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch all repositories from all projects.

        Args:
            params: Query parameters

        Yields:
            Lists of repository dictionaries
        """
        # First get all projects
        project_params = {"page_size": params.get("page_size", 100)}
        async for projects in self._paginate("/projects", project_params, 100):
            for project in projects:
                project_name = project.get("name")
                logger.debug(
                    f"Fetching repositories for project: {project_name}")

                try:
                    async for repos in self._paginate(
                        f"/projects/{project_name}/repositories",
                        params,
                        params.get("page_size", 100)
                    ):
                        yield repos
                except Exception as e:
                    logger.error(
                        f"Error fetching repos for {project_name}: {e}")
                    continue

    async def get_repository(
        self,
        project_name: str,
        repo_name: str
    ) -> Optional[dict[str, Any]]:
        """Get a single repository."""
        try:
            return await self._get(f"/projects/{project_name}/repositories/{repo_name}")
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ========================================================================
    # Artifacts API
    # ========================================================================

    async def get_all_artifacts(
        self,
        params: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch all artifacts from all projects and repositories.

        Args:
            params: Query parameters (with_tag, with_scan_overview, etc.)

        Yields:
            Lists of artifact dictionaries
        """
        # Get all repositories first
        async for repos in self.get_all_repositories({"page_size": 100}):
            for repo in repos:
                full_repo_name = repo.get("name", "")

                if "/" not in full_repo_name:
                    logger.warning(
                        f"Invalid repository name format: {full_repo_name}"
                    )
                    continue

                parts = full_repo_name.split("/", 1)
                project_name = parts[0]
                repository_name = parts[1]

                logger.debug(
                    f"Fetching artifacts for {project_name}/{repository_name}"
                )

                try:
                    async for artifacts in self._paginate(
                        f"/projects/{project_name}/repositories/{repository_name}/artifacts",
                        params,
                        params.get("page_size", 50)
                    ):
                        # Enrich artifacts with repository context
                        for artifact in artifacts:
                            artifact["repository_name"] = repository_name
                            artifact["project_name"] = project_name
                            artifact["full_repository_name"] = full_repo_name
                            # Add project_id if available in the repo object
                            if "project_id" in repo:
                                artifact["project_id"] = repo["project_id"]
                        yield artifacts
                except Exception as e:
                    logger.error(
                        f"Error fetching artifacts for {full_repo_name}: {e}"
                    )
                    continue


    async def get_artifact(
        self,
        project_name: str,
        repo_name: str,
        reference: str
    ) -> Optional[dict[str, Any]]:
        """Get a single artifact by reference (digest or tag)."""
        try:
            return await self._get(
                f"/projects/{project_name}/repositories/{repo_name}/artifacts/{reference}"
            )
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    # ========================================================================
    # Webhooks API - Previously in HarborWebhookManager
    # ========================================================================

    async def get_project_webhooks(
        self,
        project_name_or_id: str
    ) -> list[dict[str, Any]]:
        """Get all webhook policies for a project."""
        try:
            return await self._get(
                f"/projects/{project_name_or_id}/webhook/policies"
            ) or []
        except Exception as e:
            logger.error(
                f"Failed to fetch webhooks for {project_name_or_id}: {e}")
            return []

    async def create_project_webhook(
        self,
        project_name_or_id: str,
        webhook_url: str,
        webhook_name: str,
        events: list[str]
    ) -> Optional[dict[str, Any]]:
        """
        Create a webhook policy for a project.

        Args:
            project_name_or_id: Project name or ID
            webhook_url: URL to send webhook notifications to
            webhook_name: Name for the webhook policy
            events: List of event types to subscribe to

        Returns:
            Created webhook policy or None if failed
        """
        # Check if webhook already exists
        existing_webhooks = await self.get_project_webhooks(project_name_or_id)
        for webhook in existing_webhooks:
            if webhook.get("targets", [{}])[0].get("address") == webhook_url:
                logger.info(
                    f"Webhook already exists for {project_name_or_id} with URL {webhook_url}"
                )
                return webhook

        body = {
            "name": webhook_name,
            "description": "Port Ocean real-time webhook integration",
            "enabled": True,
            "event_types": events,
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "skip_cert_verify": False
                }
            ]
        }

        try:
            logger.info(f"Creating webhook for project {project_name_or_id}")
            webhook = await self._post(
                f"/projects/{project_name_or_id}/webhook/policies",
                json=body
            )
            logger.info(
                f"Successfully created webhook for {project_name_or_id}")
            return webhook
        except Exception as e:
            logger.error(
                f"Failed to create webhook for {project_name_or_id}: {e}")
            return None

    async def update_project_webhook(
        self,
        project_name_or_id: str,
        webhook_id: int,
        webhook_url: str,
        webhook_name: str,
        events: list[str]
    ) -> Optional[dict[str, Any]]:
        """Update an existing webhook policy."""
        body = {
            "name": webhook_name,
            "description": "Port Ocean real-time webhook integration",
            "enabled": True,
            "event_types": events,
            "targets": [
                {
                    "type": "http",
                    "address": webhook_url,
                    "skip_cert_verify": False,
                }
            ]
        }

        try:
            logger.info(
                f"Updating webhook {webhook_id} for {project_name_or_id}")
            await self._put(
                f"/projects/{project_name_or_id}/webhook/policies/{webhook_id}",
                json=body
            )
            logger.info(f"Successfully updated webhook {webhook_id}")

            return await self._get(
                f"/projects/{project_name_or_id}/webhook/policies/{webhook_id}"
            )
        except Exception as e:
            logger.error(f"Failed to update webhook {webhook_id}: {e}")
            return None

    async def delete_project_webhook(
        self,
        project_name_or_id: str,
        webhook_id: int
    ) -> bool:
        """Delete a webhook policy."""
        try:
            logger.info(
                f"Deleting webhook {webhook_id} for {project_name_or_id}")
            await self._delete(
                f"/projects/{project_name_or_id}/webhook/policies/{webhook_id}"
            )
            logger.info(f"Successfully deleted webhook {webhook_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete webhook {webhook_id}: {e}")
            return False
