from typing import Any, Dict, List, AsyncGenerator

import httpx
from loguru import logger

from azure_integration.clients.rest.rest_client import AzureRestClient
from azure_integration.clients.base import AzureRequest
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient


class AzureResourceManagerClient(AzureRestClient):
    """Base async Azure Resource Management client with built-in auth, rate limiting, and pagination."""

    @property
    def client(self) -> httpx.AsyncClient:
        retry_config = RetryConfig(
            retry_after_headers=[
                "Retry-After",
            ],
        )
        return OceanAsyncClient(retry_config=retry_config)

    async def make_paginated_request(
        self,
        request: AzureRequest,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Stream paginated Azure API responses efficiently in fixed-size batches."""
        next_url = request.endpoint
        batch: List[Dict[str, Any]] = []
        page_size = request.page_size

        params = {
            **request.params,
            "api-version": request.api_version,
        }

        while next_url:

            response = await self.make_request(
                AzureRequest(
                    endpoint=next_url,
                    method=request.method,
                    params=params,
                    json=request.json_body,
                    ignored_errors=request.ignored_errors,
                )
            )
            if not response:
                break

            next_url = response.get("nextLink")

            logger.info(
                f"Retrieved batch of {len(response[request.data_key])} items from {next_url} before buffering"
            )
            for item in response[request.data_key]:
                batch.append(item)
                if len(batch) == page_size:
                    yield batch
                    batch = []

        if batch:
            yield batch
