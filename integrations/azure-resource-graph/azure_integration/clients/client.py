from types import TracebackType
from typing import Any, AsyncGenerator, Sequence, cast

from azure.identity.aio import ClientSecretCredential
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
        self._auth_cred = auth_cred
        self._azure_credentials: ClientSecretCredential | None = None
        self._resource_graph_client: ResourceGraphClient | None = None

        self._rate_limiter = rate_limiter
        self._error_map = {429: AzureRequestThrottled}

    async def make_request(
        self, query: str, subscriptions: Sequence[str], **kwargs: Any
    ) -> ResponseObject:
        if not self._resource_graph_client:
            raise ValueError(
                "Azure Resource Graph Client not initialized, ensure SDKClient is run in a context manager"
            )

        query_request = QueryRequest(
            subscriptions=list(subscriptions), query=query, **kwargs
        )
        await self.handle_rate_limit(self._rate_limiter.consume(1))
        response: QueryResponse = await self._resource_graph_client.resources(
            query_request, error_map=self._error_map
        )
        return response

    async def make_paginated_request(
        self, query: str, subscriptions: Sequence[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info(f"Running query \n {query}")

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

    async def __aenter__(self) -> "SDKClient":
        self._azure_credentials = self._auth_cred.create_azure_credential()
        self._resource_graph_client = ResourceGraphClient(self._azure_credentials)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool:
        if self._resource_graph_client is not None:
            await self._resource_graph_client.close()
        if self._azure_credentials is not None:
            await self._azure_credentials.close()
        return False
