from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from clients.exceptions import DevinPaginationError

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 200


class DevinClient:
    """Thin transport layer for the Devin v3 API.

    Every org-scoped path is relative to `/v3/organizations/{org_id}`; callers
    pass `absolute_path=True` for the few endpoints that live elsewhere (the
    v3beta1 member lookup). Auth is a service-user Bearer key (`cog_...`).

    Devin does not document rate-limit headers, so `429`/`5xx` backoff is left
    to Ocean's `extensions={"retryable": True}` RetryTransport.
    """

    def __init__(
        self,
        api_host: str,
        api_key: str,
        org_id: str,
        request_timeout_seconds: int = 30,
    ) -> None:
        self._client = http_async_client
        self._api_host = api_host.rstrip("/")
        self._org_id = org_id
        self._org_base_url = f"{self._api_host}/v3/organizations/{org_id}"
        self._request_timeout_seconds = request_timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }

    @property
    def org_id(self) -> str:
        return self._org_id

    def _url(self, path: str, absolute_path: bool) -> str:
        if absolute_path:
            return f"{self._api_host}{path}"
        return f"{self._org_base_url}{path}"

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        absolute_path: bool = False,
    ) -> dict[str, Any]:
        url = self._url(path, absolute_path)
        response = await self._client.request(
            method=method,
            url=url,
            headers=self._headers,
            params=_drop_none(params),
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

    async def fetch_page(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        after: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        absolute_path: bool = False,
    ) -> dict[str, Any]:
        """Fetch one page of a Devin `items`/`end_cursor`/`has_next_page` envelope."""
        page_params = dict(params or {})
        page_params["first"] = min(page_size, MAX_PAGE_SIZE)
        if after:
            page_params["after"] = after
        return await self.send_api_request(
            "GET", path, params=page_params, absolute_path=absolute_path
        )

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Walk every page of a Devin list endpoint.

        A page that still fails after Ocean's RetryTransport has exhausted its
        retries is logged and pagination stops early so the pages already fetched
        still load; `DevinPaginationError` is then raised once at the end, which
        makes Ocean skip its delete phase so entities behind the unreachable
        remainder survive until the next resync.
        """
        after: str | None = None
        page_count = 0
        failed = False
        while True:
            try:
                payload = await self.fetch_page(path, params, after, page_size)
            except httpx.HTTPError as exc:
                failed = True
                logger.error(
                    f"Devin pagination {path}: page after cursor={after!r} failed "
                    f"after retries; stopping pagination early: {exc}"
                )
                break
            page_count += 1
            items = payload.get("items") or []
            logger.debug(
                f"Devin pagination {path}: fetched page {page_count} ({len(items)} items)"
            )
            yield items
            after = payload.get("end_cursor")
            if not payload.get("has_next_page") or not after:
                break

        if failed:
            raise DevinPaginationError(
                f"Devin pagination {path}: stopped early after {page_count} page(s) "
                "due to a request failure"
            )


def _drop_none(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """Omit unset filters; list values are sent as repeated query keys by httpx."""
    if params is None:
        return None
    return {key: value for key, value in params.items() if value is not None}
