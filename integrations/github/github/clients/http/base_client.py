from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from loguru import logger
import httpx

from github.helpers.utils import IgnoredError

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
        return (await self.authenticator.get_headers()).as_dict()

    @property
    @abstractmethod
    def base_url(self) -> str: ...

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        identifier: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        """
        Check if the error should be ignored based on the ignored errors list.
        """
        default_ignored_errors = [
            IgnoredError(
                status=401,
                message="Unauthorized access to endpoint — authentication required or token invalid",
            ),
            IgnoredError(
                status=403,
                message="Forbidden access to endpoint — insufficient permissions",
            ),
            IgnoredError(
                status=404,
                message="Resource not found at endpoint",
            ),
        ]

        if ignored_errors is None:
            ignored_errors = []

        all_ignored_errors = ignored_errors + default_ignored_errors

        for ignored_error in all_ignored_errors:

            if error.response.status_code == ignored_error.status:
                logger.info(
                    f"Ignoring error for {identifier}: {ignored_error.status} {ignored_error.message}"
                )
                return True
        return False

    async def send_api_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        return_full_response: bool = False,
        ignored_errors: Optional[List[IgnoredError]] = [],
    ) -> Any:
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
            return response if return_full_response else response.json()

        except httpx.HTTPStatusError as e:
            if self._should_ignore_error(e, resource, ignored_errors):
                return {}

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
