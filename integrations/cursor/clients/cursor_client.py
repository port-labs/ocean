from __future__ import annotations

import asyncio
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
        request_timeout_seconds: int = 30,
        max_retries: int = 5,
        backoff_seconds: float = 1.0,
    ) -> None:
        if not api_host or not str(api_host).startswith(("http://", "https://")):
            raise ValueError("cursor_api_host must be a valid http(s) URL")
        if not api_key:
            raise ValueError("cursor_api_key must be provided")

        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self._request_timeout_seconds = request_timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
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
        response = await self._request_with_retry(
            method, path, params=params, json_body=json_body
        )
        return self._parse_json(response, path)

    async def send_paginated_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield each raw page payload for Cursor's standard pagination envelope.

        `page`/`pageSize` are injected into the query string for GET requests and
        into the JSON body for everything else. Pagination continues while the
        response's `pagination.hasNextPage` flag is truthy.
        """
        page = DEFAULT_PAGE

        for _ in range(MAX_PAGES):
            page_params = dict(params or {})
            page_body = dict(json_body or {})
            if method.upper() == "GET":
                page_params.update({"page": page, "pageSize": page_size})
            else:
                page_body.update({"page": page, "pageSize": page_size})

            payload = await self.send_api_request(
                method,
                path,
                params=page_params or None,
                json_body=page_body or None,
            )

            pagination = payload.get("pagination", {}) or {}
            total_pages = pagination.get("totalPages") or pagination.get("numPages")
            progress = f"{page}/{total_pages}" if total_pages else f"{page}"
            logger.info(f"Cursor pagination {path}: fetched page {progress}")

            yield payload

            if not bool(pagination.get("hasNextPage", False)):
                break
            page += 1
        else:
            logger.warning(
                f"Cursor pagination {path}: reached MAX_PAGES safety cap ({MAX_PAGES})"
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

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = f"{self._base_url}{path}"
        limiter = self._limiter_for(path)

        for attempt in range(self._max_retries + 1):
            async with limiter:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=json_body,
                    timeout=self._request_timeout_seconds,
                )

            if response.status_code != 429:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    logger.error(
                        f"HTTP {response.status_code} for {method} {url} with params={params}"
                    )
                    raise
                return response

            if attempt == self._max_retries:
                response.raise_for_status()

            wait_seconds = self._backoff_seconds * (2**attempt)
            logger.warning(
                f"Cursor API rate limit hit on {method} {path}; retrying in {wait_seconds:.1f}s "
                f"(attempt {attempt + 1}/{self._max_retries})"
            )
            await asyncio.sleep(wait_seconds)

        raise RuntimeError("Exceeded retry attempts while calling Cursor API")
