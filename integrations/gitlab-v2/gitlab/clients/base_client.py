from typing import Any, Optional

import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
from gitlab.clients.auth_client import AuthClient
from gitlab.clients.rate_limiter import GitLabRateLimiter, GitLabRateLimiterConfig

MAX_BACKOFF_WAIT_IN_SECONDS = 1800


class HTTPBaseClient:
    def __init__(self, base_url: str, token: str, endpoint: str):
        self.token = token
        self._client = OceanAsyncClient(
            retry_config=RetryConfig(
                max_backoff_wait=MAX_BACKOFF_WAIT_IN_SECONDS,
            ),
            timeout=ocean.config.client_timeout,
        )
        self.base_url = f"{base_url}/{endpoint.strip('/')}"
        self._auth_client = AuthClient(self.token)
        self._rate_limiter = GitLabRateLimiter(GitLabRateLimiterConfig())

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

        async with self._rate_limiter:
            logger.info(f"Sending {method} request to {url}")
            response: Optional[httpx.Response] = None
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
                response = e.response
                result = await self._handle_status_code_error(
                    method, path, url, params, data, e
                )
                if result is not None:
                    return result
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP error for {method} request to {path}: {e}")
                raise
            finally:
                if response is not None:
                    self._rate_limiter.update_rate_limits(response.headers, url)

    async def _handle_status_code_error(
        self,
        method: str,
        path: str,
        url: str,
        params: dict[str, Any] | None,
        data: dict[str, Any] | None,
        e: httpx.HTTPStatusError,
    ) -> dict[str, Any] | None:
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
            return None
        if status_code in (403, 404):
            logger.warning(
                f"Resource access error at {url} (status {status_code}): {e.response.text}"
            )
            return {}
        logger.error(f"HTTP status error for {method} request to {path}: {e}")
        return None
