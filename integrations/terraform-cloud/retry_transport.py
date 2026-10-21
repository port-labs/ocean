from typing import Any

import httpx
from port_ocean.helpers.retry import RetryTransport

from rate_limiter import TerraformRateLimiter, budget_key


class RateLimitedTransport(httpx.AsyncBaseTransport):
    """Spends the rate limit budget for one HTTP attempt and records what came back."""

    def __init__(
        self,
        wrapped_transport: httpx.AsyncBaseTransport,
        rate_limiter: TerraformRateLimiter,
    ) -> None:
        self._wrapped_transport = wrapped_transport
        self._rate_limiter = rate_limiter

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        key = budget_key(request.url)
        async with self._rate_limiter.budget(key):
            response = await self._wrapped_transport.handle_async_request(request)

        self._rate_limiter.update(response.headers, key)
        return response

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
        super().__init__(
            wrapped_transport=RateLimitedTransport(wrapped_transport, rate_limiter),
            **kwargs,
        )
