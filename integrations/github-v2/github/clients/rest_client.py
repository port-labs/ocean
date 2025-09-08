import asyncio
from typing import Optional, Any, Dict

import httpx
from loguru import logger
from github.settings import SETTINGS
from port_ocean.utils import http_async_client
from port_ocean.exceptions.context import PortOceanContextNotFoundError
import time




class RestClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0, client: Optional[httpx.AsyncClient] = None):
        host =  SETTINGS.base_url or "https://api.github.com"
        self.base_url = host.rstrip("/")
        self.token = SETTINGS.token or ""
        self.client = self._init_client(timeout=timeout, client_override=client)

    def _init_client(self, timeout: float, client_override: Optional[httpx.AsyncClient] = None) -> httpx.AsyncClient:
        if client_override is not None:
            return client_override
        # Try to use Ocean's shared async client; fall back to a standalone client for tests
        try:
            client_from_ocean = http_async_client
            try:
                client_from_ocean.timeout = httpx.Timeout(timeout)
            except Exception:
                pass
            return client_from_ocean
        except PortOceanContextNotFoundError:
            return httpx.AsyncClient(timeout=httpx.Timeout(timeout))

    def _build_headers(self, token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> httpx.Response:
        token = self.token
        headers = self._build_headers(token)
        full_url = f"{self.base_url}{url}" if url.startswith("/") else url

        try:
            response = await self.client.request(
                method=method,
                url=full_url,
                headers=headers,
                params=params,
                json=json,
            )

            if response.status_code == 401:
                logger.warning(f"[RestClient] {method} {full_url} → 401. Invalid or insufficient token.")
                response.raise_for_status()

            elif response.status_code == 429:
                if retry_count >= max_retries:
                    logger.error(
                        f"[RestClient] {method} {full_url} rate limit exceeded after {max_retries} retries."
                    )
                    response.raise_for_status()

                retry_after = int(response.headers.get("Retry-After", "1"))
                logger.warning(
                    f"[RestClient] {method} {full_url} → 429. Retrying in {retry_after} seconds."
                )
                await asyncio.sleep(retry_after)
                return await self._send_api_request(
                    method, url, params, json, retry_count + 1, max_retries
                )

            elif response.status_code == 403:
                # GitHub rate limit or secondary abuse rate limit
                remaining = response.headers.get("X-RateLimit-Remaining")
                reset_at = response.headers.get("X-RateLimit-Reset")
                retry_after = response.headers.get("Retry-After")
                if (remaining == "0" and reset_at) or retry_after:
                    if retry_count >= max_retries:
                        logger.error(
                            f"[RestClient] {method} {full_url} → 403 rate limited after {max_retries} retries."
                        )
                        response.raise_for_status()
                    delay = 1
                    if retry_after:
                        try:
                            delay = int(retry_after)
                        except Exception:
                            delay = 1
                    elif reset_at:
                        try:
                            reset_epoch = int(reset_at)
                            now = int(time.time())
                            delay = max(1, reset_epoch - now + 1)
                        except Exception:
                            delay = 5
                    logger.warning(f"[RestClient] {method} {full_url} → 403 rate limited. Retrying in {delay}s")
                    await asyncio.sleep(delay)
                    return await self._send_api_request(
                        method, url, params, json, retry_count + 1, max_retries
                    )

            # Allow callers to handle 404 gracefully
            if response.status_code == 404:
                logger.warning(f"[RestClient] {method} {full_url} → 404 Not Found")
                return response
            response.raise_for_status()
            return response

        except httpx.RequestError as e:
            logger.error(f"[RestClient] {method} {full_url} request failed: {e}", exc_info=True)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"[RestClient] {method} {full_url} HTTP error: {e}", exc_info=True)
            raise

    async def get(self, url: str, params: Optional[Dict[str, Any]] = None):
        return await self._send_api_request("GET", url, params=params)

    async def post(self, url: str, json: Optional[Dict[str, Any]] = None):
        return await self._send_api_request("POST", url, json=json)

    async def put(self, url: str, json: Optional[Dict[str, Any]] = None):
        return await self._send_api_request("PUT", url, json=json)

    async def patch(self, url: str, json: Optional[Dict[str, Any]] = None):
        return await self._send_api_request("PATCH", url, json=json)

    async def delete(self, url: str):
        return await self._send_api_request("DELETE", url)

    @staticmethod
    def _extract_next_link(response: httpx.Response) -> Optional[str]:
        link_header = response.headers.get("Link")
        if not link_header:
            return None
        # Example: <https://api.github.com/resource?page=2>; rel="next", <...>; rel="last"
        parts = [p.strip() for p in link_header.split(",")]
        for part in parts:
            if 'rel="next"' in part:
                start = part.find("<")
                end = part.find(">", start + 1)
                if start != -1 and end != -1:
                    return part[start + 1 : end]
        return None

    async def get_paginated(self, url: str, params: Optional[Dict[str, Any]] = None) -> list[Any]:
        """Fetch all pages following GitHub Link headers, aggregate JSON arrays."""
        aggregated: list[Any] = []
        params = dict(params or {})
        # Maximize page size to reduce calls
        if "per_page" not in params:
            params["per_page"] = 100

        next_url: Optional[str] = f"{self.base_url}{url}" if url.startswith("/") else url
        while next_url:
            # When following absolute next links, avoid double base URL
            if next_url.startswith(self.base_url):
                path_or_url = next_url
            else:
                path_or_url = next_url

            response = await self._send_api_request("GET", path_or_url, params=params)
            try:
                data = response.json()
                if isinstance(data, list):
                    aggregated.extend(data)
                elif isinstance(data, dict):
                    # Some endpoints may return objects (shouldn't happen for list endpoints)
                    aggregated.append(data)
            except Exception:
                logger.warning("[RestClient] Failed to parse JSON page; skipping")
            next_url = self._extract_next_link(response)
            # After first page, no need to pass params; next URL includes query
            params = None

        return aggregated


