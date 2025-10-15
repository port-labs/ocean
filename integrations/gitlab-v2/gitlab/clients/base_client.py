from typing import Any, Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from gitlab.clients.auth_client import AuthClient


class HTTPBaseClient:
    def __init__(self, base_url: str, token: str, endpoint: str):
        self.token = token
        self._client = http_async_client
        self.base_url = f"{base_url}/{endpoint.strip('/')}"
        self._auth_client = AuthClient(self.token)

    @property
    def _headers(self) -> dict[str, str]:
        return self._auth_client.get_headers()

    async def _refresh_token(self) -> bool:
        """Attempt to refresh the token. Returns True if successful, False otherwise."""
        try:
            new_token = self._auth_client.get_refreshed_token()
            self.token = new_token
            self._auth_client.token = new_token
            return True
        except ValueError as e:
            logger.bind(error=str(e)).warning("External token is missing.")
            return False

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"
        logger.debug(f"Sending {method} request to {url}")

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json=data,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 401:
                # Try to refresh token and retry the request
                if await self._refresh_token():
                    try:
                        response = await self._client.request(
                            method=method,
                            url=url,
                            headers=self._headers,
                            params=params,
                            json=data,
                        )
                        response.raise_for_status()
                        return response.json()
                    except httpx.HTTPStatusError:
                        # If retry also fails, fall through to original error handling
                        pass
                raise e
            elif status_code in (403, 404):
                logger.warning(
                    f"Resource access error at {url} (status {status_code}): {e.response.text}"
                )
                return {}
            logger.error(f"HTTP status error for {method} request to {path}: {e}")
            raise

        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {method} request to {path}: {e}")
            raise
