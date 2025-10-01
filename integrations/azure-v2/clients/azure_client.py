import asyncio
from typing import Any, AsyncGenerator, Self

from loguru import logger
from .rate_limiter import TokenBucketRateLimiter

from azure.identity.aio import ClientSecretCredential
from azure.mgmt.resourcegraph.aio import ResourceGraphClient  # type: ignore
from azure.mgmt.resourcegraph.models import (  # type: ignore
    QueryRequest,
    QueryRequestOptions,
    QueryResponse,
)
from azure.mgmt.subscription.aio import SubscriptionClient
from azure.mgmt.subscription.models._models_py3 import Subscription
from port_ocean.context.ocean import ocean


class AzureClient:
    def __init__(self) -> None:
        self._credentials: ClientSecretCredential | None = None
        self.subs_client: SubscriptionClient | None = None
        self.resource_g_client: ResourceGraphClient | None = None
        # https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling#migrating-to-regional-throttling-and-token-bucket-algorithm
        self._rate_limiter = TokenBucketRateLimiter(
            capacity=250,
            refill_rate=25,
        )

    @staticmethod
    async def _handle_rate_limit(success: bool) -> None:
        if not success:
            logger.info("Rate limit exceeded, waiting for 1 second")
            await asyncio.sleep(1)

    async def get_all_subscriptions(self) -> list[Subscription]:
        logger.info("Getting all Azure subscriptions")
        if not self.subs_client:
            raise ValueError("Azure client not initialized")

        subscriptions: list[Subscription] = []
        async for sub in self.subs_client.subscriptions.list():
            await self._handle_rate_limit(self._rate_limiter.consume(1))
            subscriptions.append(sub)

        logger.info(f"Found {len(subscriptions)} subscriptions in Azure")
        return subscriptions

    async def run_query(
        self, query: str, subscriptions: list[str]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Running query")
        logger.debug(f"{query}")
        if not self.resource_g_client:
            raise ValueError("Azure client not initialized")

        skip_token: str | None = None

        while True:
            query_request = QueryRequest(
                subscriptions=subscriptions,
                query=query,
                options=QueryRequestOptions(
                    skip_token=skip_token,
                ),
            )
            await self._handle_rate_limit(self._rate_limiter.consume(1))
            response: QueryResponse = await self.resource_g_client.resources(
                query_request
            )

            logger.info("Query ran successfully")
            yield response.data
            skip_token = response.skip_token
            if not skip_token:
                logger.info("No more data to fetch")
                break
            logger.info("Fetching more data")

    async def __aenter__(self) -> Self:
        logger.info("Initializing Azure connection resources")
        self._credentials = ClientSecretCredential(
            tenant_id=ocean.integration_config["azure_tenant_id"],
            client_id=ocean.integration_config["azure_client_id"],
            client_secret=ocean.integration_config["azure_client_secret"],
        )
        self.subs_client = SubscriptionClient(self._credentials)
        self.resource_g_client = ResourceGraphClient(self._credentials)
        return self

    async def __aexit__(
        self, exc_type: Exception, exc_value: Exception, traceback: Any
    ) -> None:
        logger.info("Cleaning up Azure connection resources")
        if self.subs_client is not None:
            await self.subs_client.close()
        if self.resource_g_client is not None:
            await self.resource_g_client.close()
        if self._credentials is not None:
            await self._credentials.close()
