from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.utils import http_async_client

from core.options import (
    ListCursorAdminOptions,
    ListCursorAnalyticsOptions,
)

# Cursor enforces 20 requests/minute on the Admin API and on the AI Code Tracking API
# Limits are per-team and reset every minute. https://cursor.com/docs/api#rate-limits
DEFAULT_RATE_LIMIT_PER_MINUTE = 20

# Safety cap so a misbehaving pagination response can never loop forever.
MAX_PAGES = 10_000


class CursorClient:
    def __init__(
        self,
        api_host: str,
        api_key: str,
        request_timeout_seconds: int = 30,
        max_retries: int = 5,
        backoff_seconds: float = 1.0
    ) -> None:
        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self._request_timeout_seconds = request_timeout_seconds
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._rate_limiter = AsyncLimiter(DEFAULT_RATE_LIMIT_PER_MINUTE, 60)
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

    async def validate_analytics_connection(self) -> None:
        await self._request_with_retry(
            method="GET",
            path="/analytics/ai-code/commits",
            params={
                "startDate": "1d",
                "endDate": "0d",
                "page": 1,
                "pageSize": 1,
            },
        )
        logger.info("Cursor AI Code Tracking API connectivity validated successfully")

    async def validate_admin_connection(self) -> None:
        now = datetime.now(timezone.utc)
        await self._request_with_retry(
            method="POST",
            path="/teams/daily-usage-data",
            json_body={
                "startDate": int((now - timedelta(days=1)).timestamp() * 1000),
                "endDate": int(now.timestamp() * 1000),
                "page": 1,
                "pageSize": 1,
            },
        )
        logger.info("Cursor Admin API connectivity validated successfully")

    async def get_ai_commit_metrics(
        self, options: ListCursorAnalyticsOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for page in self._paginate_analytics(
            "/analytics/ai-code/commits", options
        ):
            yield page

    async def get_ai_change_metrics(
        self, options: ListCursorAnalyticsOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for page in self._paginate_analytics(
            "/analytics/ai-code/changes", options
        ):
            yield page

    async def get_daily_usage_data(
        self, options: ListCursorAdminOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for page in self._paginate_admin(
            "/teams/daily-usage-data",
            options,
            items_key="data",
            page_key="page",
            has_next_key="hasNextPage",
        ):
            yield page

    async def get_usage_events_data(
        self, options: ListCursorAdminOptions
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for page in self._paginate_admin(
            "/teams/filtered-usage-events",
            options,
            items_key="usageEvents",
            page_key="currentPage",
            has_next_key="hasNextPage",
        ):
            yield page

    async def _paginate_analytics(
        self,
        path: str,
        options: ListCursorAnalyticsOptions,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = options["page"]
        requested_page_size = options["pageSize"]

        for _ in range(MAX_PAGES):
            params = {
                "startDate": options["startDate"],
                "endDate": options["endDate"],
                "page": page,
                "pageSize": requested_page_size,
            }
            response = await self._request_with_retry("GET", path, params=params)
            payload = self._parse_json(response, path)

            items = payload.get("items", []) or []
            total_count = int(payload.get("totalCount", 0) or 0)
            page_size = int(payload.get("pageSize", requested_page_size) or requested_page_size)
            total_pages = (
                ceil(total_count / page_size) if page_size > 0 and total_count else None
            )
            progress = f"{page}/{total_pages}" if total_pages else f"{page}"
            logger.info(
                f"Cursor analytics {path}: fetched page {progress} ({len(items)} items)"
            )

            if items:
                yield items

            # Stop on an empty/partial page. Otherwise stop once every row has been retrieved.
            if not items or len(items) < page_size:
                break
            if total_count and page * page_size >= total_count:
                break
            page += 1
        else:
            logger.warning(
                f"Cursor analytics {path}: reached MAX_PAGES safety cap ({MAX_PAGES})"
            )

    async def _paginate_admin(
        self,
        path: str,
        options: ListCursorAdminOptions,
        items_key: str,
        page_key: str,
        has_next_key: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        page = options["page"]
        requested_page_size = options["pageSize"]

        for _ in range(MAX_PAGES):
            body = {
                "startDate": options["startDate"],
                "endDate": options["endDate"],
                "page": page,
                "pageSize": requested_page_size,
            }
            response = await self._request_with_retry("POST", path, json_body=body)
            payload = self._parse_json(response, path)

            items = payload.get(items_key, []) or []
            pagination = payload.get("pagination", {}) or {}
            current_page = int(pagination.get(page_key, page) or page)
            total_pages = pagination.get("totalPages") or pagination.get("numPages")
            progress = f"{current_page}/{total_pages}" if total_pages else f"{current_page}"
            logger.info(
                f"Cursor admin {path}: fetched page {progress} ({len(items)} items)"
            )

            if items:
                yield items

            has_next_page = bool(pagination.get(has_next_key, False))
            # Defensive: a full page with no pagination metadata most likely means
            # there is more data to fetch rather than a silent end-of-results.
            if not pagination and len(items) == requested_page_size:
                logger.warning(
                    f"Cursor admin {path}: missing pagination metadata; "
                    "continuing based on page fullness"
                )
                has_next_page = True

            if not items or not has_next_page:
                break
            page = current_page + 1
        else:
            logger.warning(
                f"Cursor admin {path}: reached MAX_PAGES safety cap ({MAX_PAGES})"
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

        for attempt in range(self._max_retries + 1):
            async with self._rate_limiter:
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
