import base64
from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from confluence.helpers.exceptions import (
    ConfluenceApiError,
    ConfluenceAuthenticationError,
    MissingConfluencePermissionError,
)

AUTH_DOCS_URL = (
    "https://developer.atlassian.com/cloud/confluence/basic-auth-for-rest-apis/"
)
TOKEN_DOCS_URL = "https://id.atlassian.com/manage-profile/security/api-tokens"


class ConfluenceClient:
    """HTTP client for one Confluence Cloud site.

    Pass a relative v2 path such as ``spaces`` or an absolute path such as
    ``/wiki/rest/api/search/user``. Cursor pagination follows ``_links.next``.
    """

    PAGE_SIZE = 100
    TIMEOUT_SECONDS = 60

    def __init__(self, site_url: str, email: str, api_token: str) -> None:
        self.site_url = site_url.rstrip("/")
        self.base_url = f"{self.site_url}/wiki/api/v2"
        self._email = email
        self._api_token = api_token
        self.http_client = http_async_client

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        missing_ok: bool = False,
    ) -> dict[str, Any]:
        """Send one request. A 404 returns an empty object only when ``missing_ok`` is set."""
        logged_endpoint = endpoint.split("?", 1)[0]
        try:
            response = await self.http_client.request(
                method=method,
                url=self._url(endpoint),
                params=params,
                headers=self._headers(),
                timeout=self.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if missing_ok and error.response.status_code == 404:
                logger.info(f"Confluence resource was not found at {logged_endpoint}")
                return {}
            self._raise_for_status(error, logged_endpoint)
        except httpx.HTTPError as error:
            logger.error(
                f"HTTP error during Confluence request to {logged_endpoint}: {error}"
            )
            raise

        try:
            payload = response.json()
        except ValueError as error:
            raise ConfluenceApiError(
                f"Confluence returned a non-JSON response for {logged_endpoint}"
            ) from error
        if not isinstance(payload, dict):
            raise ConfluenceApiError(
                f"Confluence returned an unexpected response for {logged_endpoint}"
            )
        return payload

    async def send_paginated_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield ``results`` pages until ``_links.next`` is absent."""
        next_endpoint: str | None = endpoint
        request_params = dict(params or {})
        request_params.setdefault("limit", self.PAGE_SIZE)
        next_params: dict[str, Any] | None = request_params
        seen_next: set[str] = set()

        while next_endpoint:
            payload = await self.send_api_request(next_endpoint, params=next_params)
            results = payload.get("results", [])
            if not isinstance(results, list):
                raise ConfluenceApiError(
                    f"Confluence pagination results for {next_endpoint.split('?', 1)[0]} were not a list"
                )
            if results:
                logger.info(
                    f"Fetched {len(results)} items from {next_endpoint.split('?', 1)[0]}"
                )
                yield results

            links = payload.get("_links")
            next_link = links.get("next") if isinstance(links, dict) else None
            if not isinstance(next_link, str) or not next_link.strip():
                break
            next_endpoint = next_link.strip()
            if next_endpoint in seen_next:
                logger.warning(
                    "Stopping Confluence pagination because the next link repeated"
                )
                break
            seen_next.add(next_endpoint)
            next_params = None

    def _url(self, endpoint: str) -> str:
        if endpoint.startswith(("http://", "https://")):
            return endpoint
        if endpoint.startswith("/"):
            return f"{self.site_url}{endpoint}"
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self._email}:{self._api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        }

    def _raise_for_status(self, error: httpx.HTTPStatusError, endpoint: str) -> None:
        status_code = error.response.status_code
        detail = _error_detail(error.response)
        if status_code == 401:
            message = (
                f"Confluence authentication failed for {endpoint}. "
                f"Check the Atlassian account email and API token ({TOKEN_DOCS_URL}). "
                f"Details: {detail}"
            )
            logger.error(message)
            raise ConfluenceAuthenticationError(message) from error
        if status_code == 403:
            message = (
                f"Permission denied for {endpoint}. The Atlassian account must be able to "
                "view Confluence spaces, pages, and users. "
                f"See {AUTH_DOCS_URL}. Details: {detail}"
            )
            logger.error(message)
            raise MissingConfluencePermissionError(message) from error
        logger.error(
            f"Confluence API error for {endpoint}: status {status_code}. Details: {detail}"
        )
        raise error


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:300] if text else f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            detail = errors[0].get("detail") or errors[0].get("title")
            if isinstance(detail, str) and detail.strip():
                return detail.strip()[:300]
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:300]
    return f"HTTP {response.status_code}"
