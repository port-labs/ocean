from enum import StrEnum
from typing import Any, AsyncGenerator, Optional, List
from httpx import HTTPStatusError
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from helpers.multiple_token_handler import MultiTokenBitbucketClient, TokenType

PAGE_SIZE = 100
REQUESTS_PER_HOUR = 2
WINDOW = 30


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
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send request to Bitbucket API with rate limiting."""
        url = f"{self.base_url}/{endpoint}"

        while True:  # Keep trying until request succeeds
            current_client = self.get_current_client()

            try:
                async with super().rate_limit(endpoint) as should_rotate:
                    # Even if we should rotate, make the request within this rate limit context
                    logger.debug(f"Making request to {endpoint}")
                    response = await current_client.client.request(
                        method=method, url=url, params=params, json=json_data
                    )
                    response.raise_for_status()
                    return response.json()

            except HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning(f"Rate limit hit, rotating client")
                    self._rotate_client()
                    continue
                error_data = e.response.json()
                error_message = error_data.get("error", {}).get("message", str(e))
                logger.error(f"Bitbucket API error: {error_message}")
                raise
            except Exception as e:
                logger.warning(f"Request failed, trying next client: {str(e)}")
                self._rotate_client()

            # If we should rotate after a successful request
            if should_rotate and len(self.token_clients) > 1:
                self._rotate_client()

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
            values = response["values"]
            if values:
                yield values
            next_page = response.get("next")
            if not next_page:
                break
            endpoint = next_page.replace(self.base_url + "/", "")

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"workspaces/{self.workspace}/projects"
        ):
            yield projects

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
        async for contents in self._send_paginated_api_request(
            f"repositories/{self.workspace}/{repo_slug}/src/{branch}/{path}",
            params={"max_depth": max_depth},
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
