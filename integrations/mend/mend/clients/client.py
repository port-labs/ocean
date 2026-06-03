import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from mend.auth.authenticator import MendAuthenticator
from mend.utils import IgnoredError

PAGE_SIZE = 100
_TRANSIENT_STATUS_CODES = {502, 503}
_MAX_RETRIES = 3


class MendClient:
    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=403, message="Forbidden — insufficient permissions", type="FORBIDDEN"
        ),
        IgnoredError(status=404, message="Resource not found"),
    ]

    def __init__(self, base_url: str, authenticator: MendAuthenticator) -> None:
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator
        self.org_uuid = authenticator.org_uuid

    @property
    async def auth_headers(self) -> dict[str, str]:
        return await self.authenticator.get_auth_headers()

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        all_errors = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS
        status_code = error.response.status_code
        for ie in all_errors:
            if str(status_code) == str(ie.status):
                logger.warning(f"Ignoring {status_code} at {resource}: {ie.message}")
                return True
        return False

    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        retried_auth = False
        retry_count = 0
        while True:
            try:
                logger.debug(f"Making {method} request to {url}")
                response = await http_async_client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    headers=await self.auth_headers,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status == 401 and not retried_auth:
                    logger.warning(
                        f"401 at {url} — invalidating token and retrying once"
                    )
                    await self.authenticator.invalidate_token()
                    retried_auth = True
                    continue
                if status in _TRANSIENT_STATUS_CODES and retry_count < _MAX_RETRIES:
                    retry_count += 1
                    wait = 2**retry_count
                    logger.warning(
                        f"Transient {status} at {url} — retry {retry_count}/{_MAX_RETRIES} in {wait}s"
                    )
                    await asyncio.sleep(wait)
                    continue
                if self._should_ignore_error(e, url, ignored_errors):
                    return {}
                logger.error(
                    f"HTTP {e.response.status_code} for {method} {url}: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP error during {method} {url}: {e}")
                raise

    async def send_cursor_paginated_request(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        cursor: Optional[int] = None

        while True:
            params: Dict[str, Any] = {"limit": PAGE_SIZE}
            if cursor is not None:
                params["cursor"] = cursor

            try:
                response = await self.send_api_request(
                    endpoint,
                    method=method,
                    params=params,
                    json_data=json_data,
                )
            except Exception as e:
                logger.error(f"Error in cursor paginated request to {endpoint}: {e}")
                raise

            if not response:
                break

            items: List[Dict[str, Any]] = response.get("response", [])
            if not items:
                break

            yield items

            additional_data = response.get("additionalData", {})
            if not additional_data.get("next"):
                break

            cursor = additional_data.get("cursor")
            if cursor is None:
                break
