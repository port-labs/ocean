import asyncio
from enum import StrEnum
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from httpx import HTTPStatusError
from loguru import logger
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.utils import http_async_client

from coralogix.helpers.exceptions import (
    CoralogixApiError,
    CoralogixAuthenticationError,
)
from coralogix.helpers.utils import PERMISSIONS_DOCS_URL, required_permission

PAGE_SIZE = 100
# A token that never ends, or an offset the API ignores, must not loop forever.
# Hitting the cap fails the resync so Ocean does not delete the entities it
# never reached.
MAX_PAGES = 1000
# Coralogix documents no request rate limit for these APIs; cap parallel calls
# (e.g. SLO status fan-out). Ocean's HTTP client retries 429/5xx with backoff.
MAX_CONCURRENT_REQUESTS = 10


class PaginationStyle(StrEnum):
    # `pagination.pageSize` / `pagination.pageToken` query params,
    # `pagination.nextPageToken` in the body (alerts).
    TOKEN_QUERY = "token_query"
    # `pagination` object in the JSON body, `pagination.nextPageToken` in the
    # response (cases).
    TOKEN_BODY = "token_body"


class CoralogixClient:
    """HTTP client for the Coralogix management and Metrics APIs.

    Pass a path such as ``mgmt/openapi/5/slo/slos/v1``. The API key is sent as
    a Bearer token, which both APIs accept. Pagination style is chosen by the
    exporter for each endpoint.

    Requests go through Ocean's shared ``OceanAsyncClient``, which retries
    transient failures (429, 5xx, connection errors). HTTP errors are raised.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http_client: OceanAsyncClient = http_async_client  # type: ignore[assignment]
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
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
                raise CoralogixApiError(
                    f"Coralogix returned an unexpected response for '{endpoint}'."
                )
            return payload
        except HTTPStatusError as e:
            status = e.response.status_code
            if status == 401:
                raise CoralogixAuthenticationError(
                    "Coralogix rejected the API key (HTTP 401). Check coralogixApiKey "
                    "and that coralogixApiUrl points at the key's region.",
                    status_code=status,
                ) from e
            if status == 403:
                permission = required_permission(endpoint) or "a read permission"
                message = (
                    f"Coralogix denied access to '{endpoint}' (HTTP 403). "
                    f"Grant the API key '{permission}' to sync this kind. "
                    f"See {PERMISSIONS_DOCS_URL}"
                )
                logger.error(message)
                raise CoralogixApiError(message, status_code=status) from e
            if status == 404:
                message = f"Coralogix resource '{endpoint}' was not found (HTTP 404)."
                logger.error(message)
                raise CoralogixApiError(message, status_code=status) from e
            logger.error(
                f"Coralogix API error for {method} '{endpoint}': "
                f"HTTP {status}, response: {e.response.text}"
            )
            raise
        except CoralogixApiError:
            raise
        except ValueError as e:
            raise CoralogixApiError(
                f"Coralogix returned a non-JSON response for '{endpoint}'."
            ) from e
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling Coralogix {method} {url}: {e}")
            raise

    async def send_paginated_request(
        self,
        endpoint: str,
        data_key: str,
        style: PaginationStyle,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        params = dict(params or {})
        json_data = dict(json_data or {})
        page_token: Optional[str] = None
        seen_tokens: set[str] = set()
        pages = 0

        while True:
            if pages >= MAX_PAGES:
                raise CoralogixApiError(
                    f"Stopped Coralogix pagination for '{endpoint}' after "
                    f"{MAX_PAGES} pages."
                )
            pages += 1
            request_params = dict(params)
            request_body: Optional[Dict[str, Any]] = json_data or None
            if style == PaginationStyle.TOKEN_QUERY:
                request_params["pagination.pageSize"] = page_size
                if page_token:
                    request_params["pagination.pageToken"] = page_token
            elif style == PaginationStyle.TOKEN_BODY:
                pagination: Dict[str, Any] = {"pageSize": page_size}
                if page_token:
                    pagination["pageToken"] = page_token
                request_body = {**json_data, "pagination": pagination}
            else:
                raise CoralogixApiError(
                    f"Unsupported pagination style '{style}' for '{endpoint}'."
                )

            response = await self.send_api_request(
                endpoint,
                method=method,
                params=request_params or None,
                json_data=request_body,
            )
            if data_key not in response:
                raise CoralogixApiError(
                    f"Coralogix response for '{endpoint}' did not include '{data_key}'."
                )
            items = response[data_key]
            if not isinstance(items, list):
                raise CoralogixApiError(
                    f"Expected a list at '{data_key}' from '{endpoint}', "
                    f"got {type(items).__name__}."
                )
            if items:
                logger.info(f"Fetched {len(items)} items from '{endpoint}'")
                yield items

            page_token = (response.get("pagination") or {}).get("nextPageToken")
            if not page_token or not items:
                return
            if not isinstance(page_token, str):
                raise CoralogixApiError(
                    f"Coralogix pagination for '{endpoint}' returned a page token "
                    "that is not a string."
                )
            if page_token in seen_tokens:
                raise CoralogixApiError(
                    f"Coralogix pagination for '{endpoint}' repeated a page token."
                )
            seen_tokens.add(page_token)
