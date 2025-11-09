from typing import Any, Dict, List, AsyncGenerator

import httpx
from loguru import logger

from azure_integration.clients.rest.rest_client import AzureRestClient
from azure_integration.clients.base import AzureRequest
from port_ocean.helpers.retry import RetryConfig
from port_ocean.helpers.async_client import OceanAsyncClient
from azure_integration.helpers.http import DEFAULT_HTTP_REQUEST_TIMEOUT
from itertools import batched


class AzureResourceGraphClient(AzureRestClient):
    """Base async Azure Resource Graph client with built-in auth, rate limiting, and pagination."""

    @property
    def client(self) -> httpx.AsyncClient:
        retry_config = RetryConfig(
            retry_after_headers=[
                "Retry-After",
                "x-ms-user-quota-resets-after",
            ],
            retryable_methods=[
                "POST",
                "GET",
            ],
        )
        return OceanAsyncClient(
            retry_config=retry_config, timeout=DEFAULT_HTTP_REQUEST_TIMEOUT
        )

    async def make_paginated_request(
        self,
        request: AzureRequest,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Stream paginated Azure API responses efficiently in fixed-size batches."""
        next_url = request.endpoint
        page_size = request.page_size
        skipToken = None
        page = 1
        total_fetched = 0

        json = {
            **request.json_body,
            "options": {
                "$skipToken": skipToken,
            },
        }
        params = {
            **request.params,
            "api-version": request.api_version,
        }
        while True:
            response = await self.make_request(
                AzureRequest(
                    endpoint=next_url,
                    method=request.method,
                    params=params,
                    json_body=json,
                    ignored_errors=request.ignored_errors,
                )
            )
            skipToken = response.get("$skipToken")

            json["options"]["$skipToken"] = skipToken

            logger.info(
                f"Retrieved batch of {response['count']} out of {response['totalRecords']} total records from page {page} of {next_url} before buffering"
            )
            total_fetched += response["count"]
            for item in batched(response[request.data_key], page_size):
                logger.debug(
                    f"Yielding a buffered batch of {len(item)}/{response['count']} retrieved records from page {page} of {next_url}"
                )
                yield list(item)

            logger.debug(
                f"Fetched {total_fetched} out of {response['totalRecords']} total records so far from {next_url}."
            )
            if not skipToken:
                break

            page += 1

        logger.info(
            f"Retrieved all {total_fetched}/{response['totalRecords']} total records from {next_url}"
        )
