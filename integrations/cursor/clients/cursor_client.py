from __future__ import annotations

import base64
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.utils import http_async_client

# Cursor enforces per-team rate limits that reset every minute.
# https://cursor.com/docs/api#rate-limits
#   - Admin API (`/teams/*`):                 20 requests/minute
#   - Analytics API (team-level endpoints):  100 requests/minute
#   - Analytics API (by-user endpoints):      50 requests/minute
ADMIN_RATE_LIMIT_PER_MINUTE = 20
ANALYTICS_RATE_LIMIT_PER_MINUTE = 100
ANALYTICS_BY_USER_RATE_LIMIT_PER_MINUTE = 50

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 500

# Safety cap so a misbehaving pagination response can never loop forever.
MAX_PAGES = 10_000


def _rate_limit_for_path(path: str) -> int:
    if path.startswith("/analytics/by-user"):
        return ANALYTICS_BY_USER_RATE_LIMIT_PER_MINUTE
    if path.startswith("/analytics"):
        return ANALYTICS_RATE_LIMIT_PER_MINUTE
    # `/teams/*` (Admin API) and anything else default to the strictest limit.
    return ADMIN_RATE_LIMIT_PER_MINUTE


class CursorClient:
    """Thin transport layer for the Cursor API.

    This client is intentionally resource-agnostic: it only knows how to send
    authenticated, rate-limited HTTP requests and how to walk Cursor's standard
    `pagination` envelope.
    """

    def __init__(
        self,
        api_host: str,
        api_key: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        request_timeout_seconds: int = 30,
    ) -> None:
        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self._page_size = page_size
        self._request_timeout_seconds = request_timeout_seconds
        self._rate_limiters: dict[str, AsyncLimiter] = {}
        encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {encoded_key}",
            "content-type": "application/json",
        }

    def _limiter_for(self, path: str) -> AsyncLimiter:
        limiter = self._rate_limiters.get(path)
        if limiter is None:
            limiter = AsyncLimiter(_rate_limit_for_path(path), 60)
            self._rate_limiters[path] = limiter
        return limiter

    async def validate_analytics_connection(self) -> None:
        await self.send_api_request(
            "GET",
            "/analytics/team/models",
            params={"startDate": "1d", "endDate": "0d"},
        )
        logger.info("Cursor Analytics API connectivity validated successfully")

    async def validate_admin_connection(self) -> None:
        now = datetime.now(timezone.utc)
        await self.send_api_request(
            "POST",
            "/teams/daily-usage-data",
            json_body={
                "startDate": int((now - timedelta(days=1)).timestamp() * 1000),
                "endDate": int(now.timestamp() * 1000),
                "page": 1,
                "pageSize": 1,
            },
        )
        logger.info("Cursor Admin API connectivity validated successfully")

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        async with self._limiter_for(path):
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
        except httpx.HTTPStatusError:
            logger.error(
                f"HTTP {response.status_code} for {method} {url} with params={params}"
            )
            raise

        return self._parse_json(response, path)

    async def send_paginated_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        page_size: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield each raw page payload for Cursor's standard pagination envelope.

        A page that still fails after Ocean's RetryTransport has
        exhausted its retries does not abandon the rest of the listing. Once the
        first page reports the total page count, the remaining pages are fetched
        independently; pages that fail are logged and skipped, and the generator
        raises once at the end.
        """
        page_size = page_size or self._page_size

        async def _fetch_page(page: int) -> dict[str, Any]:
            page_params = dict(params or {})
            page_body = dict(json_body or {})
            if method.upper() == "GET":
                page_params.update({"page": page, "pageSize": page_size})
            else:
                page_body.update({"page": page, "pageSize": page_size})
            return await self.send_api_request(
                method,
                path,
                params=page_params or None,
                json_body=page_body or None,
            )

        # Fetch the first page. This must succeed as it tells us how many pages exist,
        # and the rest of the pages are fetched independently.
        first_payload = await _fetch_page(DEFAULT_PAGE)
        pagination = first_payload.get("pagination", {}) or {}
        total_pages = pagination.get("totalPages") or pagination.get("numPages")
        logger.info(
            f"Cursor pagination {path}: fetched page {DEFAULT_PAGE}"
            + (f"/{total_pages}" if total_pages else "")
        )
        yield first_payload

        ## If the first page doesn't report a total, we walk `hasNextPage` as fallback.
        ## A failure here cannot be skipped (we'd lose the continuation cursor), so it propagates.
        if not total_pages:
            page = DEFAULT_PAGE
            while bool(pagination.get("hasNextPage", False)):
                page += 1
                if page > MAX_PAGES:
                    logger.warning(
                        f"Cursor pagination {path}: reached MAX_PAGES cap "
                        f"({MAX_PAGES})"
                    )
                    return
                payload = await _fetch_page(page)
                pagination = payload.get("pagination", {}) or {}
                logger.info(f"Cursor pagination {path}: fetched page {page}")
                yield payload
            return

        ## The Main loop when we know the total pages. Fetch the rest of the pages independently.
        ## pages that fail are logged and skipped, and the generator raises once at the end.
        failed_pages: list[int] = []
        for page in range(DEFAULT_PAGE + 1, int(total_pages) + 1):
            try:
                payload = await _fetch_page(page)
            except httpx.HTTPError as exc:
                failed_pages.append(page)
                logger.error(
                    f"Cursor pagination {path}: page {page}/{total_pages} failed "
                    f"after retries; skipping it and continuing with the remaining "
                    f"pages: {exc}"
                )
                continue
            logger.info(f"Cursor pagination {path}: fetched page {page}/{total_pages}")
            yield payload

        if failed_pages:
            raise RuntimeError(
                f"Cursor pagination {path}: {len(failed_pages)}/{total_pages} page(s) "
                f"failed after retries ({failed_pages}). Raising so Ocean skips its "
                "delete phase and preserves the affected entities until the next resync."
            )

    def _parse_json(self, response: httpx.Response, path: str) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            body_preview = response.text[:200] if response.text else "<empty body>"
            logger.error(
                f"Cursor API returned a non-JSON response for {path}: {body_preview}"
            )
            raise
