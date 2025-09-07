import asyncio
from typing import Optional, Any, Dict

import httpx
from loguru import logger
from github.settings import SETTINGS
from port_ocean.utils import http_async_client
from port_ocean.exceptions.context import PortOceanContextNotFoundError




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


