from json import JSONDecodeError
from typing import Any, AsyncGenerator, Optional
from httpx import HTTPError, HTTPStatusError, Response
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result
from port_ocean.context.ocean import ocean
from bitbucket_cloud.helpers.rate_limiter import RollingWindowLimiter
from bitbucket_cloud.helpers.auth import BitbucketAuthFacade, AbstractAuth
from bitbucket_cloud.helpers.token_manager import TokenRateLimiterContext, TokenManager
from bitbucket_cloud.helpers.utils import BitbucketRateLimiterConfig

PULL_REQUEST_PAGE_SIZE = 50
PAGE_SIZE = 100
RATE_LIMITER: RollingWindowLimiter = RollingWindowLimiter(
    limit=BitbucketRateLimiterConfig.LIMIT, window=BitbucketRateLimiterConfig.WINDOW
)
# The Source API's 404 body carries only this message, and it is observed, not published.
ABSENT_PATH_MESSAGE = "No such file or directory"


class BitbucketClient:
    """Client for interacting with Bitbucket Cloud API v2.0."""

    @staticmethod
    def _error_message(error: HTTPStatusError) -> Optional[str]:
        """Bitbucket's own message for a failed request.

        httpx's own string carries the status and the url but never the body, and the
        body is the only place this message appears. None when the body is not
        Bitbucket's error shape.
        """
        try:
            message = error.response.json()["error"]["message"]
        except (JSONDecodeError, KeyError, TypeError):
            return None
        return message if isinstance(message, str) else None

    @staticmethod
    def _is_absent_path(error: HTTPStatusError) -> bool:
        """Whether a Source API error says the path is not in the repository.

        An absent path, an unresolvable ref and a repository that cannot be read all
        answer 404, so the status alone cannot tell them apart. Only the error's own
        message decides, and only its start - it carries the path after the phrase. An
        unrecognised message is not absence.
        """
        if error.response.status_code != 404:
            return False
        message = BitbucketClient._error_message(error)
        return message is not None and message.startswith(ABSENT_PATH_MESSAGE)

    def __init__(
        self,
        workspace: str,
        host: str,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        user_email: Optional[str] = None,
        user_scoped_token: Optional[str] = None,
        workspace_token: Optional[str] = None,
    ) -> None:
        self.base_url = host
        self.workspace = workspace
        self.client = http_async_client

        # Initialize authentication using the facade
        self.auth: AbstractAuth = BitbucketAuthFacade.create(
            username=username,
            app_password=app_password,
            workspace_token=workspace_token,
            user_email=user_email,
            user_scoped_token=user_scoped_token,
        )

        # Set headers from authentication
        self.headers = self.auth.get_headers().dict(by_alias=True)
        self.client.headers.update(self.headers)

    @property
    def token_manager(self) -> Optional[TokenManager]:
        """Get the token manager if using multi-token authentication."""
        if hasattr(self.auth, "token_manager"):
            return self.auth.token_manager
        return None

    @token_manager.setter
    def token_manager(self, value: TokenManager) -> None:
        """Set the token manager for testing purposes."""
        if hasattr(self.auth, "_token_manager"):
            self.auth._token_manager = value

    @property
    def file_token_manager(self) -> Optional[TokenManager]:
        """Get the file token manager if using multi-token authentication."""
        if hasattr(self.auth, "file_token_manager"):
            return self.auth.file_token_manager
        return None

    def _update_authorization_header(self, token: str) -> None:
        """Update the authorization header with a new token."""
        self.headers["Authorization"] = f"Bearer {token}"
        self.client.headers.update(self.headers)

    @classmethod
    def create_from_ocean_config(cls) -> "BitbucketClient":
        return cls(
            workspace=ocean.integration_config["bitbucket_workspace"],
            host=ocean.integration_config["bitbucket_host_url"],
            username=ocean.integration_config.get("bitbucket_username"),
            app_password=ocean.integration_config.get("bitbucket_app_password"),
            user_email=ocean.integration_config.get("bitbucket_user_email"),
            user_scoped_token=ocean.integration_config.get(
                "bitbucket_user_scoped_token"
            ),
            workspace_token=ocean.integration_config.get("bitbucket_workspace_token"),
        )

    async def _send_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
        return_full_response: bool = False,
        raise_on_missing: bool = False,
    ) -> Any:
        """Send request to Bitbucket API with error handling."""
        response = await self.client.request(
            method=method, url=url, params=params, json=json_data
        )
        try:
            response.raise_for_status()
            return response if return_full_response else response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                if raise_on_missing:
                    raise
                logger.warning(
                    f"Requested resource not found: {url}; "
                    f"{self._error_message(e) or 'no message in the response body'}"
                )
                return {}
            logger.error(f"Bitbucket API error: {str(e)}")
            raise
        except HTTPError as e:
            logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
            raise

    async def _fetch_paginated_api_with_rate_limiter(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        data_key: str = "values",
        raise_on_missing: bool = False,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {"pagelen": PAGE_SIZE, **(params or {})}
        while True:
            if hasattr(self.auth, "token_manager") and self.auth.token_manager:
                async with TokenRateLimiterContext(self.auth.token_manager) as ctx:
                    current_token = ctx.get_token()
                    self._update_authorization_header(current_token)
                    response = await self._send_api_request(
                        url,
                        params=params,
                        method=method,
                        raise_on_missing=raise_on_missing,
                    )
            else:
                async with RATE_LIMITER:
                    response = await self._send_api_request(
                        url,
                        params=params,
                        method=method,
                        raise_on_missing=raise_on_missing,
                    )

            values: list[dict[str, Any]] = response.get(data_key, [])
            if not values:
                break

            yield values

            url = response.get("next")
            params = None
            if not url:
                break

    async def _send_file_api_request_with_rate_limiter(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        return_full_response: bool = False,
        raise_on_missing: bool = False,
    ) -> Any:
        """Send file-specific API request with dedicated file rate limiter."""
        if hasattr(self.auth, "file_token_manager") and self.auth.file_token_manager:
            async with TokenRateLimiterContext(self.auth.file_token_manager) as ctx:
                current_token = ctx.get_token()
                self._update_authorization_header(current_token)
                response = await self._send_api_request(
                    url,
                    params=params,
                    method=method,
                    return_full_response=return_full_response,
                    raise_on_missing=raise_on_missing,
                )
        else:
            # No file token manager means single token or basic auth - just make the request
            response = await self._send_api_request(
                url,
                params=params,
                method=method,
                return_full_response=return_full_response,
                raise_on_missing=raise_on_missing,
            )
        return response

    async def _send_paginated_api_request(
        self,
        url: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
        data_key: str = "values",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle Bitbucket's pagination for API requests with a flexible data key.
        Args:
            url: The API endpoint to request.
            params: Optional dictionary of query parameters.
            method: The HTTP method to use.
            data_key: The key to use when extracting data from the API response.
        Yields:
            Lists of dictionaries containing the paginated data.
        """
        params = {"pagelen": PAGE_SIZE, **(params or {})}
        while True:
            response = await self._send_api_request(url, params=params, method=method)
            if values := response.get(data_key, []):
                yield values
            url = response.get("next")
            if not url:
                break
            params = None

    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all projects in the workspace."""
        async for projects in self._send_paginated_api_request(
            f"{self.base_url}/workspaces/{self.workspace}/projects"
        ):
            logger.info(
                f"Fetched batch of {len(projects)} projects from workspace {self.workspace}"
            )
            yield projects

    @cache_iterator_result()
    async def get_repositories(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get all repositories in the workspace."""
        async for repos in self._fetch_paginated_api_with_rate_limiter(
            f"{self.base_url}/repositories/{self.workspace}", params=params
        ):
            logger.info(
                f"Fetched batch of {len(repos)} repositories from workspace {self.workspace}"
            )
            yield repos

    async def get_directory_contents(
        self,
        repo_slug: str,
        branch: str,
        path: str,
        max_depth: int,
        params: Optional[dict[str, Any]] = None,
        raise_on_missing: bool = False,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get contents of a directory.

        Left alone, any 404 reports no contents, as every other endpoint on this client
        does and as the folder kind's two callers expect. raise_on_missing instead fails
        on an unresolvable ref or a repository that cannot be read - which also answer
        404 - and tolerates only a path this repository does not have.
        """
        # Least to most specific: module default, the caller's params, then what it named.
        params = {"pagelen": PAGE_SIZE, **(params or {}), "max_depth": max_depth}
        first_page_seen = False
        try:
            async for contents in self._fetch_paginated_api_with_rate_limiter(
                f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/src/{branch}/{path}",
                params=params,
                raise_on_missing=raise_on_missing,
            ):
                first_page_seen = True
                logger.info(
                    f"Fetched directory contents batch with {len(contents)} contents"
                )
                yield contents
        except HTTPStatusError as e:
            # A root cannot legitimately 404, and past the first page the path provably existed.
            if (
                raise_on_missing
                and path
                and not first_page_seen
                and self._is_absent_path(e)
            ):
                logger.warning(
                    f"Path '{path}' is not in repository {repo_slug}, reporting no contents"
                )
                return
            raise

    async def get_pull_requests(
        self, repo_slug: str, params: dict[str, Any] = {}
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get pull requests for a repository."""
        params["pagelen"] = PULL_REQUEST_PAGE_SIZE
        async for pull_requests in self._fetch_paginated_api_with_rate_limiter(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests",
            params=params,
        ):
            logger.info(
                f"Fetched batch of {len(pull_requests)} pull requests from repository {repo_slug} in workspace {self.workspace}"
            )
            yield pull_requests

    async def get_pull_request(
        self, repo_slug: str, pull_request_id: str
    ) -> dict[str, Any]:
        """Get a specific pull request by ID."""
        return await self._send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}/pullrequests/{pull_request_id}"
        )

    async def get_repository(self, repo_slug: str) -> dict[str, Any]:
        """Get a specific repository by slug."""
        return await self._send_api_request(
            f"{self.base_url}/repositories/{self.workspace}/{repo_slug}"
        )

    async def get_repository_files(
        self, repo: str, branch: str, path: str
    ) -> Optional[str]:
        """Get the content of a file, or None if Bitbucket cannot return it."""
        url = (
            f"{self.base_url}/repositories/{self.workspace}/{repo}/src/{branch}/{path}"
        )
        try:
            response: Response = await self._send_file_api_request_with_rate_limiter(
                url,
                method="GET",
                return_full_response=True,
                raise_on_missing=True,
            )
        except HTTPStatusError as e:
            if self._is_absent_path(e):
                logger.warning(
                    f"Bitbucket returned no content for {url}; {self._error_message(e)}"
                )
                return None
            raise
        logger.info(f"Retrieved file content for {repo}/{branch}/{path}")
        return response.text
