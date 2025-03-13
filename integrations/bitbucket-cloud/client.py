from enum import StrEnum
from typing import Any, AsyncGenerator, Optional, List, Dict
from httpx import HTTPStatusError
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from helpers.multiple_token_handler import MultiTokenBitbucketClient, TokenType

PAGE_SIZE = 100
REQUESTS_PER_HOUR = 950
WINDOW = 3600


class ObjectKind(StrEnum):
    PROJECT = "project"
    FOLDER = "folder"
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"


class BitbucketClient(MultiTokenBitbucketClient):
    """Client for interacting with Bitbucket Cloud API v2.0."""

    def __init__(
        self,
        workspace: str,
        credentials: List[TokenType],
        requests_per_hour: int = REQUESTS_PER_HOUR,
        window: int = WINDOW,
    ) -> None:
        super().__init__(
            credentials=credentials, requests_per_hour=requests_per_hour, window=window
        )
        self.workspace = workspace

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        """Create BitbucketClient from ocean config."""
        workspace = ocean.integration_config["bitbucket_workspace"]
        credentials: List[TokenType] = []

        # Collect workspace tokens
        if tokens := ocean.integration_config.get("bitbucket_workspace_token", ""):
            credentials.extend(
                token.strip() for token in tokens.split(",") if token.strip()
            )

        # Collect username/password pairs
        usernames = ocean.integration_config.get("bitbucket_username", "").split(",")
        passwords = ocean.integration_config.get("bitbucket_app_password", "").split(
            ","
        )

        if any(usernames) and any(passwords):
            username_list = [u.strip() for u in usernames if u.strip()]
            password_list = [p.strip() for p in passwords if p.strip()]

            if len(username_list) != len(password_list):
                raise ValueError(
                    "Number of usernames does not match number of passwords"
                )

            credentials.extend(zip(username_list, password_list))

        if not credentials:
            raise ValueError(
                "No valid credentials found in config. Provide either:\n"
                "- bitbucket_workspace_token: comma-separated tokens\n"
                "- or both bitbucket_username and bitbucket_app_password"
            )

        logger.info(f"Initializing BitbucketClient with {len(credentials)} credentials")
        return cls(workspace=workspace, credentials=credentials)

    async def _send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        url: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Send a request to the Bitbucket API with automatic retries and rate limiting.

        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method
            params: Query parameters
            json: JSON body for POST/PUT requests

        Returns:
            Response data as JSON

        Raises:
            HTTPStatusError: If the request fails and cannot be retried
        """
        logger.debug(f"Making request to {endpoint}")

        max_retries = len(self.token_clients)
        for attempt in range(max_retries):
            current_client = self.get_current_client()
            url = url or f"{self.base_url}/{endpoint}"

            try:
                # Apply rate limiting if this is a repository endpoint
                async with self.rate_limit(endpoint) as should_rotate:
                    if should_rotate:
                        self._rotate_client()
                        current_client = self.get_current_client()

                    response = await current_client.client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                    )
                    response.raise_for_status()
                    return response.json()

            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limit hit, rotate to next client
                    logger.warning("Rate limit hit, rotating client")
                    self._rotate_client()
                    if attempt < max_retries - 1:
                        continue
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(e))
                logger.error(f"Bitbucket API error: {error_msg}")
                raise

            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                raise

    async def _send_paginated_api_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Send a paginated request to the Bitbucket API.

        Args:
            endpoint: API endpoint (without base URL)
            params: Optional query parameters

        Yields:
            Batches of values from each page
        """
        if params is None:
            params = {}
        next_page = None
        while True:
            response = await self._send_api_request(
                endpoint, params=params, url=next_page
            )
            if values := response.get("values", []):
                yield values
            next_page = response.get("next")
            if not next_page:
                break

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"workspaces/{self.workspace}/projects"
        ):
            yield projects

    @cache_iterator_result()
    async def get_repositories(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._send_paginated_api_request(
            f"repositories/{self.workspace}"
        ):
            yield repos

    async def get_directory_contents(
        self, repo_slug: str, ref: str, path: str = "", max_depth: int = 2
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get contents of a directory in a repository.

        Args:
            repo_slug: Repository slug
            ref: Branch or commit reference
            path: Directory path (empty for root)
            max_depth: Maximum depth to recurse

        Yields:
            Batches of directory contents
        """
        # Clean up path
        clean_path = path.strip("/")
        if clean_path:
            clean_path = f"{clean_path}/"

        endpoint = f"repositories/{self.workspace}/{repo_slug}/src/{ref}/{clean_path}"
        params = {"max_depth": max_depth, "pagelen": 100}

        async for contents in self._send_paginated_api_request(endpoint, params=params):
            yield contents

    async def get_pull_requests(
        self, repo_slug: str, state: str = "OPEN"
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """
        Get pull requests for a repository.

        Args:
            repo_slug: Repository slug
            state: Pull request state (OPEN, MERGED, DECLINED, etc.)

        Yields:
            Batches of pull requests
        """
        endpoint = f"repositories/{self.workspace}/{repo_slug}/pullrequests"
        params = {}
        if state:
            params["state"] = state

        async for prs in self._send_paginated_api_request(endpoint, params=params):
            yield prs
