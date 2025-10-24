from typing import Any, Optional, Dict, List, cast

import httpx
from loguru import logger

from azure_integration.helpers.rate_limiter import (
    AdaptiveTokenBucketRateLimiter,
)
from azure.core.credentials_async import AsyncTokenCredential

from azure_integration.clients.base import AbstractAzureClient, AzureRequest
from abc import abstractmethod


class AzureRestClient(AbstractAzureClient):
    """Base async Azure REST client with built-in auth, rate limiting, and pagination."""

    _DEFAULT_IGNORED_ERRORS = [
        dict(status=401, message="Unauthorized — invalid or expired credentials"),
        dict(status=403, message="Forbidden — insufficient Azure permissions"),
        dict(status=404, message="Resource not found"),
    ]

    def __init__(
        self,
        credential: AsyncTokenCredential,
        base_url: str,
        rate_limiter: AdaptiveTokenBucketRateLimiter,
        **kwargs: Any,
    ) -> None:
        self.credential: AsyncTokenCredential = credential
        self.base_url: str = base_url
        self.rate_limiter: AdaptiveTokenBucketRateLimiter = rate_limiter

    @property
    @abstractmethod
    def client(self) -> httpx.AsyncClient:
        """An abstract property representing the async HTTP client."""
        pass

    @property
    def scope(self) -> str:
        """Azure Resource scope used for token acquisition (e.g., https://management.azure.com/.default)."""
        return self.base_url + "/.default"

    async def get_headers(self) -> Dict[str, str]:
        token = (await self.credential.get_token(self.scope)).token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def make_request(
        self,
        request: AzureRequest,
    ) -> Dict[str, Any]:
        """Make a request to Azure API with rate limiting and error handling."""
        endpoint: str = cast(str, request.endpoint)
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        logger.info(f"Making request to {url} with params {request.params}")
        async with self.rate_limiter.limit():
            try:
                headers = await self.get_headers()
                response = await self.client.request(
                    method=request.method,
                    url=url,
                    params=request.params,
                    json=request.json_body,
                    headers=headers,
                )
                response.raise_for_status()
                logger.info(f"Successfully fetched {request.method} {url}")
                logger.error(f"Response headers for {url}: {response.headers}")
                self.rate_limiter.adjust_from_headers(dict(response.headers))
                return response.json()

            except httpx.HTTPStatusError as e:
                response = e.response
                if self._should_ignore_error(e, request.ignored_errors):
                    return {}

                logger.error(
                    f"Azure API error for '{url}': "
                    f"Status {response.status_code}, Response: {response.text}"
                )
                raise

            except httpx.HTTPError as e:
                logger.error(f"Network error for endpoint '{url}': {str(e)}")
                raise

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        ignored_errors: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        ignored = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS
        for entry in ignored:
            if str(error.response.status_code) == str(entry["status"]):
                logger.warning(f"Ignored Azure error: {entry['message']}")
                return True
        return False
