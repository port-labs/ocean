from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from utils.http import DEFAULT_PAGE_SIZE, build_list_page_params, drop_none


class DevinPaginationError(Exception):
    # Raising after a partial list makes Ocean skip delete for unfetched pages.
    pass


class DevinClient:
    def __init__(self, api_host: str, api_key: str, org_id: str) -> None:
        self._client = http_async_client
        self._api_host = api_host.rstrip("/")
        self._org_id = org_id
        self._org_base_url = f"{self._api_host}/v3/organizations/{org_id}"
        self._headers = {"Authorization": f"Bearer {api_key}"}

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
            params=drop_none(params),
            json=json_body,
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        *,
        envelopes: bool = False,
    ) -> AsyncGenerator[Any, None]:
        base_params = dict(params or {})
        after: str | None = base_params.pop("after", None)
        page_count = 0
        failed = False
        while True:
            try:
                payload = await self.send_api_request(
                    "GET",
                    path,
                    params=build_list_page_params(
                        base_params, after=after, page_size=page_size
                    ),
                )
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
            yield payload if envelopes else items
            after = payload.get("end_cursor")
            if not payload.get("has_next_page") or not after:
                break

        if failed:
            raise DevinPaginationError(
                f"Devin pagination {path}: stopped early after {page_count} page(s) "
                "due to a request failure"
            )
