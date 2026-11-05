from typing import Any

import httpx
from port_ocean.helpers.retry import RetryTransport

from rate_limiter import TerraformRateLimiter, budget_key


class RateLimitedTransport(httpx.AsyncBaseTransport):
    """Spends the rate limit budget for one HTTP attempt."""

    def __init__(
        self,
        wrapped_transport: httpx.AsyncBaseTransport,
        rate_limiter: TerraformRateLimiter,
    ) -> None:
        self._wrapped_transport = wrapped_transport
        self._rate_limiter = rate_limiter

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        async with self._rate_limiter.budget(budget_key(request.url)):
            return await self._wrapped_transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self._wrapped_transport.aclose()


class TerraformRetryTransport(RetryTransport):
    """Rate limits each attempt rather than each call.

    RetryTransport replays a retryable response up to ten times. A limiter held around
    the whole call never sees those replays, so they spend the budget unaccounted for
    and sustain the 429s that triggered them.
    """

    def __init__(
        self,
        *,
        rate_limiter: TerraformRateLimiter,
        wrapped_transport: httpx.AsyncBaseTransport,
        **kwargs: Any,
    ) -> None:
        self._rate_limiter = rate_limiter
        super().__init__(
            wrapped_transport=RateLimitedTransport(wrapped_transport, rate_limiter),
            **kwargs,
        )

    async def after_retry_async(
        self, request: httpx.Request, response: httpx.Response, attempt: int
    ) -> None:
        # Not reached for POST, which the framework does not retry; budget() has
        # already spent for it.
        self._rate_limiter.update(response.headers, budget_key(request.url))
