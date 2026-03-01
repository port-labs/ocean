from typing import Any, AsyncGenerator, Literal
from urllib.parse import urljoin

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from harbor.helpers.exceptions import (
    ForbiddenError,
    HarborAPIError,
    NotFoundError,
    ServerError,
    UnauthorizedError,
)
from harbor.helpers.utils import IgnoredError


class HarborClient:
    """Harbor API v2.0 client - handles HTTP requests only."""

    PAGE_SIZE = 100
    API_VERSION = "v2.0"

    HTTP_401_UNAUTHORIZED = 401
    HTTP_403_FORBIDDEN = 403
    HTTP_404_NOT_FOUND = 404
    HTTP_429_RATE_LIMIT_EXCEEDED = 429
    HTTP_500_INTERNAL_SERVER_ERROR = 500

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(status=404, message="Resource not found"),
        IgnoredError(status=403, message="Access forbidden"),
    ]

    def __init__(self, base_url: str, username: str, password: str) -> None:
        """Initialize Harbor client.

        Args:
            base_url: Harbor instance URL (e.g., https://harbor.example.com)
            username: Harbor username or robot account
            password: Harbor password or robot token
        """
        self._base_url_raw = base_url.rstrip('/')
        self.auth = httpx.BasicAuth(username, password)
        self._csrf_token: str | None = None

        logger.info(f"Initialized Harbor client for {self.base_url}")

    @property
    def base_url(self) -> str:
        """Compute the full API base URL."""
        api_suffix = f"/api/{self.API_VERSION}"

        if self._base_url_raw.endswith(api_suffix):
            return self._base_url_raw
        return f"{self._base_url_raw}{api_suffix}"

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
    ) -> bool:
        """Check if error should be gracefully ignored."""
        status_code = error.response.status_code

        for ignored_error in self._DEFAULT_IGNORED_ERRORS:
            if status_code == ignored_error.status:
                logger.warning(f"Failed to fetch {resource}: {ignored_error.message}")
                return True
        return False

    def _cache_csrf_token(self, response: httpx.Response) -> None:
        """Extract and cache CSRF token from Harbor response headers.

        Harbor returns CSRF tokens in X-Harbor-CSRF-Token header for write operations.
        We cache this token to reuse in subsequent write requests (POST/PUT/DELETE).
        """
        if csrf_token := response.headers.get("X-Harbor-CSRF-Token"):
            self._csrf_token = csrf_token
            logger.debug("Cached CSRF token from Harbor response")

    async def _ensure_csrf_token(self) -> str:
        """Ensure CSRF token is available for write operations.

        Harbor v2.0+ requires CSRF tokens for all write operations (POST/PUT/DELETE)
        as a security measure against Cross-Site Request Forgery attacks.

        The token is obtained by making a GET request to /systeminfo and caching
        the X-Harbor-CSRF-Token header. Subsequent write operations reuse this token.
        """
        if self._csrf_token:
            logger.debug("Using cached CSRF token")
            return self._csrf_token

        logger.info("Fetching CSRF token from Harbor /systeminfo endpoint")

        try:
            url = urljoin(self.base_url + '/', "systeminfo")

            response = await http_async_client.request(
                method="GET",
                url=url,
                auth=self.auth,
            )
            response.raise_for_status()

            self._cache_csrf_token(response)

            if not self._csrf_token:
                raise HarborAPIError("Harbor did not return CSRF token in response headers")

            logger.info("Successfully obtained CSRF token")
            return self._csrf_token

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch CSRF token: {e}")
            raise HarborAPIError(f"Failed to obtain CSRF token: {e}") from e

    async def send_api_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        method: Literal['POST', 'GET', 'PUT', 'DELETE'] = 'GET',
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        """Send request to Harbor API with authentication and CSRF protection.

        For write operations (POST/PUT/DELETE), automatically obtains and includes
        CSRF token as required by Harbor v2.0+.
        """
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))

        # harbor requires CSRF tokens for write operations
        is_write_operation = method in {'POST', 'PUT', 'PATCH', 'DELETE'}

        headers: dict[str, str] = {}

        if is_write_operation:
            csrf_token = await self._ensure_csrf_token()
            headers["X-Harbor-CSRF-Token"] = csrf_token
            logger.debug(f"Added CSRF token to {method} request")

        logger.debug(f"Harbor API {method} {url} with params: {params}")

        try:
            response = await http_async_client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                auth=self.auth,
                json=json_data,
            )
            response.raise_for_status()

            # Cache CSRF token from response for future use
            self._cache_csrf_token(response)

            return response.json()

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            if self._should_ignore_error(e, endpoint):
                logger.debug(f"Returning empty list for ignored error: {status_code}")
                return []

            match status_code:
                case self.HTTP_401_UNAUTHORIZED:
                    logger.error(f"Authentication failed for {url}")
                    raise UnauthorizedError(
                        "Authentication failed. Check Harbor credentials", self.HTTP_401_UNAUTHORIZED
                    ) from e

                case self.HTTP_403_FORBIDDEN:
                    logger.error(f"Permission denied for {url}")
                    raise ForbiddenError(
                        "Permission denied. Check Harbor user permissions", self.HTTP_403_FORBIDDEN
                    ) from e

                case self.HTTP_404_NOT_FOUND:
                    resource = endpoint.split("/")[-1] if "/" in endpoint else endpoint
                    logger.warning(f"Resource not found: {url}")
                    raise NotFoundError(resource) from e

                case _ if status_code >= self.HTTP_500_INTERNAL_SERVER_ERROR:
                    logger.error(f"Harbor server error ({status_code}) for {url}")
                    raise ServerError(f"Harbor server error: {status_code}", status_code) from e

                case _:
                    logger.error(f"Harbor API error ({status_code}) for {url}")
                    raise HarborAPIError(f"API error: {status_code}", status_code) from e

        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise

    async def send_paginated_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle Harbor's pagination for API requests.

        Harbor uses page-based pagination with page and page_size parameters.
        This method automatically handles pagination and yields results page by page.
        """
        if params is None:
            params = {}

        params["page_size"] = self.PAGE_SIZE
        page = 1

        logger.info(f"Starting pagination for {endpoint}")

        while True:
            params["page"] = page
            items = await self.send_api_request(endpoint, params=params)

            if not items:
                logger.info(f"Completed pagination for {endpoint} after {page - 1} pages")
                break

            logger.debug(f"Fetched page {page}: {len(items)} items")
            yield items
            page += 1
