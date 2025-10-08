from __future__ import annotations

from types import TracebackType
from typing import AsyncContextManager, AsyncGenerator
from azure.identity.aio import ClientSecretCredential
from azure.mgmt.subscription.aio import SubscriptionClient
from azure.mgmt.subscription.models import Subscription
from loguru import logger
from azure_integration.helpers.rate_limiter import (
    RateLimitHandler,
    TokenBucketRateLimiter,
)
from azure_integration.models import AuthCredentials


class SubscriptionManager(RateLimitHandler, AsyncContextManager["SubscriptionManager"]):
    """
    Manages fetching of Azure subscriptions, handling authentication and rate limiting.

    This class acts as an asynchronous context manager to properly handle the lifecycle
    of Azure SDK clients. It provides methods to retrieve subscriptions in batches to
    avoid overwhelming the API and to manage memory efficiently.
    """

    def __init__(
        self,
        auth_cred: AuthCredentials,
        rate_limiter: TokenBucketRateLimiter,
        batch_size: int = 1000,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._subs_client: SubscriptionClient | None = None
        self._azure_credentials: ClientSecretCredential | None = None
        self._auth_cred = auth_cred
        self._batch_size = batch_size
        logger.info(f"Subscription manager initialized with a batch of {batch_size}")

    async def get_subscription_batches(
        self,
    ) -> AsyncGenerator[list[Subscription], None]:
        if not self._subs_client:
            raise ValueError("Azure subscription client not initialized")
        subscriptions: list[Subscription] = []
        async for sub in self._subs_client.subscriptions.list():
            await self.handle_rate_limit(self._rate_limiter.consume(1))
            subscriptions.append(sub)
            if len(subscriptions) >= self._batch_size:
                yield subscriptions
                subscriptions = []

        if subscriptions:
            yield subscriptions

    async def get_sub_id_in_batches(self) -> AsyncGenerator[list[str], None]:
        async for sub_batch in self.get_subscription_batches():
            yield [
                str(s.subscription_id)
                for s in sub_batch
                if s.subscription_id is not None
            ]

    async def __aenter__(self) -> "SubscriptionManager":
        self._azure_credentials = self._auth_cred.create_azure_credential()
        self._subs_client = SubscriptionClient(self._azure_credentials)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool:
        if self._subs_client is not None:
            await self._subs_client.close()
        if self._azure_credentials is not None:
            await self._azure_credentials.close()
        return False
