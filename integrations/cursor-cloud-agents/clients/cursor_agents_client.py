from __future__ import annotations

import base64
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from clients.exceptions import CursorAgentsPaginationError

DEFAULT_PAGE_SIZE = 20


class CursorAgentsClient:
    """Thin transport layer for the Cursor Cloud Agents API (v0 and v1).

    v0 (`/v0/agents*`) is the legacy, webhook-capable API; v1 (`/v1/agents*`) is
    the current API with richer create/follow-up options but no webhooks yet.
    Both share the same durable agent store and Basic-auth API key, so a single
    client exposes both surfaces rather than splitting into two clients.

    Cursor's Cloud Agents API does not expose rate-limit state via response
    headers, so there is no proactive pacing here - `429`/`5xx` backoff is left
    to Ocean's `extensions={"retryable": True}` RetryTransport (exponential
    backoff), same as the `cursor` (usage metrics) integration's client.
    """

    def __init__(
        self,
        api_host: str,
        api_key: str,
        console_host: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        request_timeout_seconds: int = 30,
    ) -> None:
        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self._console_host = console_host.rstrip("/")
        self._page_size = page_size
        self._request_timeout_seconds = request_timeout_seconds
        encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {encoded_key}",
            "content-type": "application/json",
        }

    @property
    def page_size(self) -> int:
        return self._page_size

    def get_console_host(self) -> str:
        return self._console_host

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = await self._client.request(
            method=method,
            url=url,
            headers=self._headers,
            params=params,
            json=json_body,
            timeout=self._request_timeout_seconds,
            extensions={"retryable": True},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            message = (
                f"HTTP {response.status_code} for {method} {url}: "
                f"{response.text[:200]}"
            )
            logger.error(message)
            raise httpx.HTTPStatusError(
                message, request=error.request, response=error.response
            ) from error
        if not response.content:
            return {}
        return response.json()

    async def paginate_by_cursor(
        self,
        path: str,
        items_key: str,
        params: dict[str, Any] | None = None,
        page_size: int | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Walk a Cursor `<items_key>`/`nextCursor` pagination envelope.
        `nextCursor` is omitted (not null) once there are no more pages.

        A page that still fails after Ocean's RetryTransport has exhausted its
        retries is logged and pagination stops early so the pages already fetched
        still load; `CursorAgentsPaginationError` is then raised once at the end,
        which makes Ocean skip its delete phase so entities behind the
        unreachable remainder survive until the next resync.
        """
        page_size = page_size or self._page_size
        base_params = dict(params or {})
        base_params["limit"] = page_size

        cursor: str | None = None
        page_count = 0
        failed = False
        while True:
            page_params = dict(base_params)
            if cursor:
                page_params["cursor"] = cursor
            try:
                payload = await self.send_api_request("GET", path, params=page_params)
            except httpx.HTTPError as exc:
                failed = True
                logger.error(
                    f"Cursor pagination {path}: page after cursor={cursor!r} failed "
                    f"after retries; stopping pagination early: {exc}"
                )
                break
            page_count += 1
            items = payload.get(items_key) or []
            logger.info(
                f"Cursor pagination {path}: fetched page {page_count} ({len(items)} items)"
            )
            yield items
            cursor = payload.get("nextCursor")
            if not cursor:
                break

        if failed:
            raise CursorAgentsPaginationError(
                f"Cursor pagination {path}: stopped early after {page_count} page(s) "
                "due to a request failure"
            )
