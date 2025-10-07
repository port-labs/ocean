from typing import Any, AsyncGenerator, Sequence, cast

from azure.mgmt.resourcegraph.aio import ResourceGraphClient  # type: ignore
from azure.mgmt.resourcegraph.models import (  # type: ignore
    QueryRequest,
    QueryRequestOptions,
    QueryResponse,
)
from loguru import logger

from azure_integration.clients.base import AzureClient, ResponseObject
from azure_integration.errors import AzureRequestThrottled
from azure_integration.helpers.rate_limiter import TokenBucketRateLimiter
from azure_integration.models import AuthCredentials

from azure_integration.helpers.rate_limiter import RateLimitHandler


class SDKClient(AzureClient, RateLimitHandler):
    def __init__(
        self, auth_cred: AuthCredentials, rate_limiter: TokenBucketRateLimiter
    ) -> None:
        self._azure_credentials = auth_cred.create_azure_credential()
        self.resource_g_client = ResourceGraphClient(self._azure_credentials)
        # https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling#migrating-to-regional-throttling-and-token-bucket-algorithm
        self._rate_limiter = rate_limiter
        self._error_map = {429: AzureRequestThrottled}

    async def make_request(
        self, query: str, subscriptions: Sequence[str], **kwargs
    ) -> ResponseObject:
        query_request = QueryRequest(
            subscriptions=list(subscriptions), query=query, **kwargs
        )
        await self.handle_rate_limit(self._rate_limiter.consume(1))
        response: QueryResponse = await self.resource_g_client.resources(
            query_request, error_map=self._error_map
        )
        return response

    async def make_paginated_request(
        self, query: str, subscriptions: Sequence[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Running query")
        logger.debug(f"{query}")
        if not self.resource_g_client:
            raise ValueError("Azure client not initialized")

        skip_token: str | None = None

        while True:
            try:
                query_options = QueryRequestOptions(skip_token=skip_token)
                res = await self.make_request(
                    query, subscriptions, options=query_options
                )
                logger.info("Query ran successfully")
                yield res.data

                response = cast(QueryResponse, res)
                skip_token = response.skip_token
                if not skip_token:
                    logger.info("No more data to fetch")
                    break
                logger.info("Fetching more data")
            except AzureRequestThrottled as e:
                logger.warning("Azure request is getting throttled while running query")
                await e.handle_delay()
