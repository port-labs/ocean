from __future__ import annotations

import base64
from typing import Any, AsyncGenerator

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

PAGE_SIZE = 100
PUBLIC_API_PREFIX = "/api/public"


class LangfuseClient:
    """Generic HTTP transport for the Langfuse public API. Resource paths live in exporters."""

    def __init__(self, host: str, public_key: str, secret_key: str) -> None:
        self.base_url = f"{host.rstrip('/')}{PUBLIC_API_PREFIX}"
        encoded = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self.http_client = http_async_client

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = await self.http_client.request(
            method=method,
            url=url,
            headers=self._headers,
            params=params,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                logger.warning(f"Langfuse resource not found at {endpoint}")
                return {}
            logger.error(
                f"Langfuse API error for '{endpoint}': "
                f"{error.response.status_code} {error.response.text[:200]}"
            )
            raise
        if not response.content:
            return {}
        return response.json()

    async def send_paginated_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data_key: str = "data",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Page-based pagination (`page`/`limit` + `meta.totalPages`)."""
        page = 1
        base_params = {**(params or {}), "limit": PAGE_SIZE}

        while True:
            response = await self.send_api_request(
                endpoint, params={**base_params, "page": page}
            )
            if not response:
                break

            items = response.get(data_key) or []
            if not isinstance(items, list):
                logger.error(f"Unexpected {data_key!r} payload from {endpoint}")
                break

            if items:
                logger.info(f"Fetched {len(items)} items from {endpoint} page {page}")
                yield items

            meta = response.get("meta") or {}
            total_pages = meta.get("totalPages")
            if total_pages is None or page >= int(total_pages) or not items:
                break
            page += 1

    async def send_cursor_paginated_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data_key: str = "data",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Cursor pagination (`meta.cursor`). Empty page can still have a cursor."""
        cursor: str | None = None
        base_params = {**(params or {}), "limit": PAGE_SIZE}

        while True:
            req_params = {**base_params}
            if cursor:
                req_params["cursor"] = cursor

            response = await self.send_api_request(endpoint, params=req_params)
            if not response:
                break

            items = response.get(data_key) or []
            if not isinstance(items, list):
                logger.error(f"Unexpected {data_key!r} payload from {endpoint}")
                break

            if items:
                logger.info(
                    f"Fetched {len(items)} items from {endpoint}"
                    f"{f' cursor={cursor[:16]}…' if cursor else ''}"
                )
                yield items

            cursor = (response.get("meta") or {}).get("cursor")
            if not cursor:
                break
