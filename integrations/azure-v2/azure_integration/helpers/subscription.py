from typing import AsyncGenerator
from azure.mgmt.subscription.aio import SubscriptionClient
from azure.mgmt.subscription.models import Subscription
from loguru import logger
from azure_integration.helpers.rate_limiter import (
    RateLimitHandler,
    TokenBucketRateLimiter,
)
from azure_integration.models import AuthCredentials


class SubscriptionManager(RateLimitHandler):
    def __init__(
        self,
        auth_cred: AuthCredentials,
        rate_limiter: TokenBucketRateLimiter,
        batch_size: int = 1000,
    ) -> None:
        self._rate_limiter = rate_limiter
        self.subs_client = SubscriptionClient(auth_cred.create_azure_credential())
        self.batch_size = batch_size

    async def get_all_subscriptions(self) -> list[Subscription]:
        logger.info("Getting all Azure subscriptions")
        if not self.subs_client:
            raise ValueError("Azure subscription client not initialized")

        subscriptions: list[Subscription] = []
        async for sub in self.subs_client.subscriptions.list():
            await self.handle_rate_limit(self._rate_limiter.consume(1))
            subscriptions.append(sub)

        logger.info(f"Found {len(subscriptions)} subscriptions in Azure")
        return subscriptions

    async def get_subscription_batches(
        self,
    ) -> AsyncGenerator[list[Subscription], None]:
        subscriptions: list[Subscription] = []
        async for sub in self.subs_client.subscriptions.list():
            await self.handle_rate_limit(self._rate_limiter.consume(1))
            subscriptions.append(sub)
            if len(subscriptions) >= self.batch_size:
                yield subscriptions
                subscriptions = []

        if subscriptions:
            yield subscriptions
