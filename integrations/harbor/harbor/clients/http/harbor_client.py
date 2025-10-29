from typing import Any, Dict, List, Optional, AsyncGenerator
from urllib.parse import urljoin
import httpx
import re

from ..auth.abstract_authenticator import AbstractHarborAuthenticator
from loguru import logger
from harbor.helpers.utils import IgnoredError
from harbor.helpers.exceptions import InvalidTokenException


DEFAULT_PAGE_SIZE = 100


class HarborClient:
    """Harbor API v2.0 client using Ocean's async HTTP client"""

    NEXT_PATTERN = re.compile(r'<([^>]+)>; rel="next"')

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(status=404, message="Resource not found"),
        IgnoredError(status=403, message="Access forbidden"),
    ]

    def __init__(
        self, harbor_host: str, authenticator: AbstractHarborAuthenticator
    ) -> None:
        self._authenticator = authenticator
        self._base_url = harbor_host.rstrip("/")
        self.api_url = f"{self._base_url}/api/v2.0"
        self.client = self._authenticator.client

        logger.info(f"Harbor client initialized for {harbor_host}")

    @property
    def base_url(self) -> str:
        return self._base_url

    def _get_next_link(self, link_header: str) -> Optional[str]:
        match = self.NEXT_PATTERN.search(link_header)
        return match.group(1) if match else None

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        all_ignored_errors = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS
        status_code = error.response.status_code

        for ignored_error in all_ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Failed to fetch resources at {resource} due to {ignored_error.message}"
                )
                return True
        return False

    async def make_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[Any]] = None,
    ) -> httpx.Response:
        """Make a request to the Harbor API with authentication and error handling."""
        url = urljoin(self.api_url + "/", resource.lstrip("/"))

        headers = await self._authenticator.get_headers()
        headers_dict = headers.as_dict()

        logger.debug(f"Harbor API {method} {url} with params: {params}")

        # Harbor's API issues a session ID cookie (`sid`) during GET requests,
        # which is meant for UI sessions (the Harbor web interface) and enforces CSRF checks
        # on subsequent modifying requests (POST, PUT, PATCH).
        #
        # When we authenticate using Basic Auth programmatically (like in our Ocean client),
        # these cookies are unnecessary and can cause CSRF validation errors:
        #     {"code": "FORBIDDEN", "message": "CSRF token not found in request"}
        #
        # To avoid this, we clear cookies before any write operation so the request behaves
        # like a stateless API call.
        if method in ["POST", "PUT", "PATCH"]:
            self.client.cookies.clear()

        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers_dict,
            )
            response.raise_for_status()

            logger.debug(f"Successfully fetched {method} {url}")
            return response

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise InvalidTokenException()

            if self._should_ignore_error(e, url, ignored_errors):
                return httpx.Response(200, content=b"{}")

            logger.error(
                f"Harbor API error for endpoint '{url}': Status {e.response.status_code}, "
                f"Method: {method}, Response: {e.response.text}"
            )
            raise

        except httpx.HTTPError as e:
            logger.error(f"HTTP error for endpoint '{url}': {str(e)}")
            raise

    async def send_paginated_request(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle Harbor's pagination for API requests."""
        if params is None:
            params = {}

        params["page_size"] = DEFAULT_PAGE_SIZE

        logger.info(f"Starting pagination for {method} {resource}")

        while True:
            response = await self.make_request(
                resource,
                method=method,
                params=params,
                ignored_errors=ignored_errors,
            )

            if not response or not (items := response.json()):
                break

            yield items

            if not (link_header := response.headers.get("Link")) or not (
                next_resource := self._get_next_link(link_header)
            ):
                break

            params = None
            resource = next_resource
