from typing import Any, AsyncGenerator, Optional
from httpx import HTTPStatusError, Timeout
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
import base64
from enum import StrEnum

PAGE_SIZE = 100
CLIENT_TIMEOUT = 30

class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"


class BitbucketClient:
    """Client for interacting with Bitbucket Cloud API v2.0."""

    def __init__(
        self,
        workspace: str,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        workspace_token: Optional[str] = None,
    ) -> None:
        self.base_url = "https://api.bitbucket.org/2.0"
        self.workspace = workspace
        self.client = http_async_client
        self.client.timeout = Timeout(CLIENT_TIMEOUT)

        if workspace_token:
            self.headers = {
                "Authorization": f"Bearer {workspace_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        elif app_password and username:
            self.encoded_credentials = base64.b64encode(
                f"{username}:{app_password}".encode()
            ).decode()
            self.headers = {
                "Authorization": f"Basic {self.encoded_credentials}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        else:
            raise ValueError(
                "Either workspace_token or both username and app_password must be provided"
            )
        self.client.headers.update(self.headers)

    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        url = f"{self.base_url}/{endpoint}"
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as e:
            error_data = e.response.json()
            error_message = error_data.get("error", {}).get("message", str(e))
            logger.error(f"Bitbucket API error: {error_message}")

    async def _send_paginated_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle Bitbucket's pagination for API requests."""
        if params is None:
            params = {}

        while True:
            response = await self._send_api_request(
                endpoint, params=params, method=method
            )
            values = response.get("values", [])
            if values:
                yield values
            next_page = response.get("next")
            if not next_page:
                break
            endpoint = next_page.replace(self.base_url + "/", "")

    # Project endpoints
    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"workspaces/{self.workspace}/projects"
        ):
            yield projects

    # Repository endpoints
    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_paginated_api_request(
            f"repositories/{self.workspace}"
        ):
            yield repos

    async def get_directory_contents(
        self, repo_slug: str, branch: str, path: str, max_depth: int = 2
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get contents of a directory."""
        params = {
            "max_depth": max_depth,
            "pagelen": PAGE_SIZE,
        }
        async for contents in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/src/{branch}/{path}",
            params=params,
        ):
            yield contents

    async def get_pull_requests(
        self, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        async for pull_requests in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/pullrequests"
        ):
            yield pull_requests

    async def get_pull_request(self, repo_slug: str, pull_request_id: str) -> dict[str, Any]:
        """Get a specific pull request by ID."""
        return await self._send_api_request(
            f"repositories/{self.workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        )

    async def get_repository(self, repo_slug: str) -> dict[str, Any]:
        """Get a specific repository by slug."""
        return await self._send_api_request(
            f"repositories/{self.workspace}/{repo_slug}"
        )

    async def create_webhooks(self, callback_url: str) -> None:
        """Create webhooks for all repositories in the workspace."""
        logger.info("Setting up Bitbucket webhooks")
        
        # Define the webhook configuration
        webhook_config = {
            "description": "Port DevPortal Integration",
            "url": callback_url,
            "active": True,
            "events": [
                "pullrequest:created",
                "pullrequest:updated",
                "pullrequest:approved",
                "pullrequest:unapproved",
                "pullrequest:fulfilled",
                "pullrequest:rejected",
                "pullrequest:deleted",
                "pullrequest:comment_created",
                "pullrequest:comment_updated",
                "pullrequest:comment_deleted"
            ]
        }

        # Get all repositories and create webhooks for each
        async for repositories in self.get_repositories():
            for repo in repositories:
                repo_slug = repo.get("slug", repo["name"].lower())
                
                try:
                    # Check if webhook already exists
                    existing_webhooks = await self._send_api_request(
                        f"repositories/{self.workspace}/{repo_slug}/hooks"
                    )
                    
                    webhook_exists = any(
                        hook.get("url") == callback_url 
                        for hook in existing_webhooks.get("values", [])
                    )
                    
                    if webhook_exists:
                        logger.info(
                            f"Webhook already exists for repository {repo_slug}, skipping"
                        )
                        continue

                    # Create webhook if it doesn't exist
                    await self._send_api_request(
                        f"repositories/{self.workspace}/{repo_slug}/hooks",
                        method="POST",
                        json_data=webhook_config
                    )
                    logger.info(f"Successfully created webhook for repository {repo_slug}")
                    
                except Exception as e:
                    logger.error(
                        f"Failed to create webhook for repository {repo_slug}: {str(e)}"
                    )
