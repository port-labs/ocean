from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)

from loguru import logger
import httpx
from httpx import Response

if TYPE_CHECKING:
    from github.clients.auth.abstract_authenticator import (
        AbstractGitHubAuthenticator,
    )


class AbstractGithubClient(ABC):
    def __init__(
        self,
        organization: str,
        github_host: str,
        authenticator: "AbstractGitHubAuthenticator",
        **kwargs: Any,
    ) -> None:
        self.organization = organization
        self.github_host = github_host
        self.authenticator = authenticator
        self.kwargs = kwargs

    @property
    async def headers(self) -> Dict[str, str]:
        """Build and return headers for GitHub API requests."""
        header = self.authenticator.get_headers().as_dict()
        return header

    @property
    @abstractmethod
    def base_url(self) -> str: ...

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Response:
        """Send request to GitHub API with error handling and rate limiting."""

        try:
            response = await self.authenticator.client.request(
                method=method,
                url=resource,
                params=params,
                json=json_data,
                headers=await self.headers,
            )
            response.raise_for_status()

            logger.debug(f"Successfully fetched {method} {resource}")
            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug(f"Resource not found at endpoint '{resource}'")
                return e.response
            logger.error(
                f"GitHub API error for endpoint '{resource}': Status {e.response.status_code}, "
                f"Method: {method}, Response: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for endpoint '{resource}': {str(e)}")
            raise

    @abstractmethod
    def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Send a paginated request to GitHub API and yield results.

        Args:
            resource: The API resource path
            params: Query parameters or variables
            method: HTTP method

        Yields:
            Lists of items from paginated responses
        """
        pass
