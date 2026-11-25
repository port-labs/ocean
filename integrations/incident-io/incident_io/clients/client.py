import asyncio
import time
from collections import deque
from typing import Any, AsyncGenerator, Optional

import httpx
from httpx import HTTPStatusError
from loguru import logger
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.utils import http_async_client

from incident_io.helpers.exceptions import (
    IncidentIoApiError,
    IncidentIoAuthenticationError,
)
from incident_io.helpers.utils import PERMISSIONS_DOCS_URL, required_permission

PAGE_SIZE = 100
MAX_PAGES = 1000
# List incidents is capped at 60/minute (the other list endpoints share the
# 1200/minute key limit, which refills at 20/second). Stay under both.
INCIDENT_REQUESTS_PER_MINUTE = 50
DEFAULT_REQUESTS_PER_SECOND = 20
MAX_CONCURRENT_REQUESTS = 5


class _WindowLimiter:
    """Small sliding-window limiter so this integration needs no extra package."""

    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self._max_calls = max_calls
        self._period = period_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self._period:
                    self._timestamps.popleft()
                if len(self._timestamps) < self._max_calls:
                    self._timestamps.append(now)
                    return
                wait = self._period - (now - self._timestamps[0])
            await asyncio.sleep(max(wait, 0.01))


class IncidentIoClient:
    """HTTP client for the incident.io API.

    Pass a path such as ``v2/incidents``. The API key is sent as a Bearer
    token. Pagination is ``page_size`` plus the ``after`` cursor from
    ``pagination_meta``. ``after`` is the last id on the page, including the
    final page, so an empty following page ends the loop.

    Requests go through Ocean's shared ``OceanAsyncClient``, which retries
    transient failures (429, 5xx, connection errors). HTTP errors are raised.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http_client: OceanAsyncClient = http_async_client  # type: ignore[assignment]
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._incident_limiter = _WindowLimiter(INCIDENT_REQUESTS_PER_MINUTE, 60)
        self._default_limiter = _WindowLimiter(DEFAULT_REQUESTS_PER_SECOND, 1)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

    def _limiter_for(self, endpoint: str) -> _WindowLimiter:
        path = endpoint.lstrip("/")
        if path == "v2/incidents" or path.startswith("v2/incidents/"):
            return self._incident_limiter
        return self._default_limiter

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            await self._limiter_for(endpoint).acquire()
            async with self._semaphore:
                response = await self._http_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=self._headers(),
                    timeout=60,
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise IncidentIoApiError(
                    f"incident.io returned an unexpected response for '{endpoint}'."
                )
            return payload
        except HTTPStatusError as error:
            status = error.response.status_code
            if status == 401:
                raise IncidentIoAuthenticationError(
                    "incident.io rejected the API key (HTTP 401). Check incidentIoApiKey.",
                    status_code=status,
                ) from error
            if status == 403:
                permission = required_permission(endpoint) or "access to this endpoint"
                message = (
                    f"incident.io denied access to '{endpoint}' (HTTP 403). "
                    f"Grant the API key {permission}. See {PERMISSIONS_DOCS_URL}"
                )
                logger.error(message)
                raise IncidentIoApiError(message, status_code=status) from error
            if status == 404:
                message = f"incident.io resource '{endpoint}' was not found (HTTP 404)."
                logger.error(message)
                raise IncidentIoApiError(message, status_code=status) from error
            logger.error(
                f"incident.io API error for {method} '{endpoint}': HTTP {status}"
            )
            raise
        except IncidentIoApiError:
            raise
        except ValueError as error:
            raise IncidentIoApiError(
                f"incident.io returned a non-JSON response for '{endpoint}'."
            ) from error
        except httpx.HTTPError as error:
            logger.error(f"HTTP error calling incident.io {method} {url}: {error}")
            raise

    async def send_paginated_request(
        self,
        endpoint: str,
        data_key: str,
        params: Optional[dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = dict(params or {})
        page_token: Optional[str] = None
        seen_tokens: set[str] = set()
        pages = 0

        while True:
            if pages >= MAX_PAGES:
                raise IncidentIoApiError(
                    f"Stopped incident.io pagination for '{endpoint}' after "
                    f"{MAX_PAGES} pages."
                )
            pages += 1
            request_params = dict(params)
            request_params["page_size"] = page_size
            if page_token:
                request_params["after"] = page_token

            response = await self.send_api_request(endpoint, params=request_params)
            if data_key not in response:
                raise IncidentIoApiError(
                    f"incident.io response for '{endpoint}' did not include '{data_key}'."
                )
            items = response[data_key]
            if not isinstance(items, list):
                raise IncidentIoApiError(
                    f"Expected a list at '{data_key}' from '{endpoint}', "
                    f"got {type(items).__name__}."
                )
            if items:
                logger.info(f"Fetched {len(items)} items from '{endpoint}'")
                yield items

            meta = response.get("pagination_meta") or {}
            page_token = meta.get("after") if isinstance(meta, dict) else None
            # The last page still returns `after` set to its last id. The
            # following request is empty and omits `after`.
            if not items or not page_token:
                return
            if not isinstance(page_token, str):
                raise IncidentIoApiError(
                    f"incident.io pagination for '{endpoint}' returned a page token "
                    "that is not a string."
                )
            if page_token in seen_tokens:
                raise IncidentIoApiError(
                    f"incident.io pagination for '{endpoint}' repeated a page token."
                )
            seen_tokens.add(page_token)
