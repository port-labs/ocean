from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client


class ClaudeClient:
    def __init__(self, api_host: str, api_key: str, anthropic_version: str) -> None:
        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": anthropic_version,
            "content-type": "application/json",
        }

    async def get_usage_report_messages(
        self,
        params: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yields pages of usage report message records."""
        async for page in self._paginate(
            "/v1/organizations/usage_report/messages", params
        ):
            yield page

    async def get_cost_report(
        self,
        params: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yields pages of cost report records."""
        async for page in self._paginate("/v1/organizations/cost_report", params):
            yield page

    async def get_claude_code_report(
        self,
        params: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yields pages of Claude Code analytics records.

        Soft-fails (yields nothing) when Claude Code is not enabled for the
        organisation (HTTP 403), rather than crashing the resync.
        """
        async for page in self._paginate(
            "/v1/organizations/usage_report/claude_code",
            params,
            soft_fail_statuses={403},
        ):
            yield page

    async def _paginate(
        self,
        path: str,
        params: dict[str, Any],
        soft_fail_statuses: set[int] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Follow pagination cursors and yield one page of records at a time.

        Args:
            path: API path to request.
            params: Initial query parameters.
            soft_fail_statuses: HTTP status codes that should cause the
                generator to stop silently instead of raising.
        """
        current_params = dict(params)

        while True:
            response = await self._send_request(
                path=path,
                params=current_params,
                soft_fail_statuses=soft_fail_statuses,
            )
            if response is None:
                return

            payload = response.json()

            if not isinstance(payload, dict):
                logger.warning(
                    f"Unexpected response shape from {path}: expected a JSON object, "
                    f"got {type(payload).__name__}. Stopping pagination."
                )
                return

            records = payload.get("data")
            if records:
                yield records

            # Follow the next page if one is present
            next_page = payload.get("next_page")
            has_more = payload.get("has_more", False)

            if not has_more or not next_page:
                break

            current_params = {**current_params, "page": next_page}

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

            if soft_fail_statuses and status_code in soft_fail_statuses:
                logger.warning(
                    f"Received HTTP {status_code} for {url}. "
                    "This endpoint may not be available for your organisation "
                    "(e.g. Claude Code not enabled). Skipping."
                )
                return None

            logger.error(f"HTTP {status_code} error for {url}: {error}")
            raise
        except httpx.HTTPError as error:
            logger.error(
                f"Unexpected HTTP error occurred while making GET request to {url}: {str(error)}"
            )
            raise
