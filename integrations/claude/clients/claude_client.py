from __future__ import annotations

from collections.abc import AsyncGenerator
from enum import StrEnum
from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client


class ClaudeDeployment(StrEnum):
    """Which Claude offering the integration is configured against."""

    ENTERPRISE = "enterprise"
    PLATFORM = "platform"


# Hard cap on the number of pages a single paginated request will follow. Guards
# against an endpoint that keeps echoing a non-null next_page cursor, which would
# otherwise loop forever.
MAX_PAGES = 10_000


class ClaudeClient:
    """Thin async HTTP client for the Anthropic API.

    The client only owns concerns that are shared across every kind:
    authentication, single requests, pagination and graceful handling of
    rate limits / permission errors.
    """

    def __init__(
        self,
        api_host: str,
        api_key: str,
        anthropic_version: str,
        deployment: ClaudeDeployment = ClaudeDeployment.ENTERPRISE,
    ) -> None:
        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self.deployment = deployment
        self._headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
        }
        # The Claude Platform reports require the anthropic-version header;
        if deployment == ClaudeDeployment.PLATFORM:
            self._headers["anthropic-version"] = anthropic_version

    async def send_paginated_request(
        self,
        path: str,
        params: dict[str, Any],
        soft_fail_statuses: set[int] | None = None,
        page_param: str = "page",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Follow pagination cursors and yield one page of records at a time.
        Args:
            path: API path to request.
            params: Initial query parameters.
            soft_fail_statuses: HTTP status codes that should stop the
                generator silently instead of raising (e.g. 403 when the
                key lacks the required scope).
            page_param: Query parameter used to pass the next-page cursor.
        """
        current_params = dict(params)

        for page_number in range(1, MAX_PAGES + 1):
            payload = await self.send_api_request(
                path=path,
                params=current_params,
                soft_fail_statuses=soft_fail_statuses,
            )
            if payload is None:
                return

            records = payload.get("data")
            if records:
                yield records

            next_page = payload.get("next_page")
            has_more = payload.get("has_more")

            # No cursor → nothing more to fetch. Some endpoints (users) omit
            # ``has_more`` entirely and simply return a null ``next_page``.
            if not next_page:
                break
            # When ``has_more`` is explicitly present and False, stop even if a
            # stale cursor is echoed back.
            if has_more is False:
                break

            if page_number == MAX_PAGES:
                logger.warning(
                    f"Reached the {MAX_PAGES}-page limit for {path}; stopping "
                    "pagination. Some records may not have been fetched."
                )
                break

            current_params = {**current_params, page_param: next_page}

    async def send_api_request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        soft_fail_statuses: set[int] | None = None,
    ) -> dict[str, Any] | None:
        """Perform a single GET request and return the JSON object body.

        Returns ``None`` when the request soft-fails or when the response is
        not a JSON object.
        """
        response = await self._send_request(
            path=path,
            params=params or {},
            soft_fail_statuses=soft_fail_statuses,
        )
        if response is None:
            return None

        payload = response.json()
        if not isinstance(payload, dict):
            logger.warning(
                f"Unexpected response shape from {path}: expected a JSON object, "
                f"got {type(payload).__name__}. Ignoring."
            )
            return None
        return payload

    async def _send_request(
        self,
        path: str,
        params: dict[str, Any],
        soft_fail_statuses: set[int] | None = None,
    ) -> httpx.Response | None:
        url = f"{self._base_url}{path}"

        logger.info(f"GET {url} — params: {params}")

        try:
            response = await self._client.request(
                method="GET",
                url=url,
                headers=self._headers,
                params=params,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            status_code = error.response.status_code
            body = error.response.text

            if soft_fail_statuses and status_code in soft_fail_statuses:
                logger.warning(
                    f"Received HTTP {status_code} for {url}. "
                    "This endpoint may not be available for your organisation "
                    "or your API key may lack the required scope. Skipping. "
                    f"Response body: {body}"
                )
                return None

            logger.error(
                f"HTTP {status_code} error for {url}: {error}. "
                f"Response body: {body}"
            )
            raise
        except httpx.HTTPError as error:
            logger.error(
                f"Unexpected HTTP error occurred while making GET request to {url}: {str(error)}"
            )
            raise
