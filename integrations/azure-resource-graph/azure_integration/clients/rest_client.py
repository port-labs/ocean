from typing import Any, Optional, Dict, List, AsyncGenerator, cast

import httpx
from loguru import logger

from azure_integration.helpers.rate_limiter import (
    AdaptiveTokenBucketRateLimiter,
)
from azure.core.credentials_async import AsyncTokenCredential

from azure_integration.clients.base import AbstractAzureClient, AzureRequest
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
from memory_profiler import profile


class AzureRestClient(AbstractAzureClient):
    """Base async Azure REST client with built-in auth, rate limiting, and pagination."""

    _DEFAULT_IGNORED_ERRORS = [
        dict(status=401, message="Unauthorized — invalid or expired credentials"),
        dict(status=403, message="Forbidden — insufficient Azure permissions"),
        dict(status=404, message="Resource not found"),
    ]

    def __init__(
        self, credential: AsyncTokenCredential, base_url: str, **kwargs: Any
    ) -> None:
        self.credential: AsyncTokenCredential = credential
        self.base_url: str = base_url
        self.kwargs: Any = kwargs
        self.rate_limiter: AdaptiveTokenBucketRateLimiter = (
            AdaptiveTokenBucketRateLimiter(capacity=250, refill_rate=25)
        )

    @property
    def client(self) -> httpx.AsyncClient:
        retry_config = RetryConfig(
            retry_after_headers=[
                "Retry-After",
                "x-ms-user-quota-resets-after",
            ],
        )
        return OceanAsyncClient(retry_config=retry_config)

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

    @profile
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
                    json=request.json_data,
                    headers=headers,
                )
                response.raise_for_status()
                logger.info(f"Successfully fetched {request.method} {url}")
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

    async def make_paginated_request(
        self,
        request: AzureRequest,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Stream paginated Azure API responses efficiently in fixed-size batches."""
        next_url = request.endpoint
        batch: List[Dict[str, Any]] = []
        page_size = request.page_size

        while next_url:
            params = {
                **(request.params or {}),
                "api-version": request.api_version,
                "page_size": page_size,
            }

            response = await self.make_request(
                AzureRequest(
                    endpoint=next_url,
                    method=request.method,
                    params=params,
                    json_data=request.json_data,
                    ignored_errors=request.ignored_errors,
                )
            )
            if not response:
                break

            next_url = response.get("nextLink")

            for item in response[request.data_key]:
                batch.append(item)
                if len(batch) == page_size:
                    yield batch
                    batch = []

        if batch:
            yield batch
