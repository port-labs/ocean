from typing import Any, Optional

import httpx
from loguru import logger
from port_ocean.utils import http_async_client

from github.clients.auth_client import AuthClient

# We need TYPE_CHECKING for the github_client forward reference
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from github.clients.github_client import GitHubClient


class HTTPBaseClient:
    def __init__(
        self, base_url: str, token: str, github_client: Optional["GitHubClient"] = None
    ):
        self.token = token
        self._client = http_async_client
        auth_client = AuthClient(token)
        self._headers = auth_client.get_headers()
        self.base_url = f"{base_url}"
        self._github_client = github_client  # Store the client reference

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        bypass_rate_limiter: bool = False,  # New flag
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path}"

        if (
            not bypass_rate_limiter
            and self._github_client
            and hasattr(self._github_client, "rate_limiter")
        ):
            await self._github_client.rate_limiter.acquire(self._github_client)

        logger.debug(f"Sending {method} request to GitHub API: {url}")

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=self._headers,
                params=params,
                json=data,
            )

            # Update rate limiter from headers, if available and not bypassed
            if (
                not bypass_rate_limiter
                and self._github_client
                and hasattr(self._github_client, "rate_limiter")
            ):
                self._github_client.rate_limiter.update_from_headers(
                    dict(response.headers)
                )

            response.raise_for_status()

            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    f"GitHub API resource not found at {url} for params {params}"
                )
                return {}
            # Potentially handle 429/403 specifically if not fully handled by limiter
            logger.error(
                f"GitHub API HTTP status error for {method} request to {path}: {e}"
            )
            raise

        except httpx.HTTPError as e:
            logger.error(f"GitHub API HTTP error for {method} request to {path}: {e}")
            raise
