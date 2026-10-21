from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import pytest

from rate_limiter import TerraformRateLimiter
from retry_transport import RateLimitedTransport, TerraformRetryTransport


class CountingLimiter(TerraformRateLimiter):
    """Records what the transport spends, without pausing the test."""

    def __init__(self) -> None:
        super().__init__()
        self.acquisitions = 0
        self.updates: list[str] = []

    @asynccontextmanager
    async def budget(self, key: str) -> AsyncIterator[None]:
        self.acquisitions += 1
        yield

    def update(self, headers: httpx.Headers, key: str) -> None:
        self.updates.append(key)
        super().update(headers, key)


class ScriptedTransport(httpx.AsyncBaseTransport):
    def __init__(self, *status_codes: int) -> None:
        self.status_codes = list(status_codes)
        self.attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        status = self.status_codes.pop(0) if self.status_codes else 200
        return httpx.Response(status, json={"data": []}, request=request)


def build(
    *status_codes: int,
) -> tuple[TerraformRetryTransport, ScriptedTransport, CountingLimiter]:
    wrapped = ScriptedTransport(*status_codes)
    limiter = CountingLimiter()
    transport = TerraformRetryTransport(
        rate_limiter=limiter,
        wrapped_transport=wrapped,
        base_delay=0.001,
        logger=None,
    )
    return transport, wrapped, limiter


class TestRateLimitedTransport:
    @pytest.mark.asyncio
    async def test_acquires_once_per_request(self) -> None:
        limiter = CountingLimiter()
        wrapped = ScriptedTransport(200)
        transport = RateLimitedTransport(wrapped, limiter)

        await transport.handle_async_request(
            httpx.Request("GET", "https://app.terraform.io")
        )

        assert limiter.acquisitions == 1
        assert wrapped.attempts == 1


class TestTerraformRetryTransport:
    @pytest.mark.asyncio
    async def test_acquires_for_every_retried_attempt(self) -> None:
        transport, wrapped, limiter = build(429, 429, 200)

        response = await transport.handle_async_request(
            httpx.Request("GET", "https://app.terraform.io/api/v2/workspaces")
        )

        assert response.status_code == 200
        assert wrapped.attempts == 3
        # The point of the subclass: a limiter around the call would have counted 1.
        assert limiter.acquisitions == 3

    @pytest.mark.asyncio
    async def test_acquires_once_when_no_retry_is_needed(self) -> None:
        transport, wrapped, limiter = build(200)

        await transport.handle_async_request(
            httpx.Request("GET", "https://app.terraform.io/api/v2/workspaces")
        )

        assert wrapped.attempts == 1
        assert limiter.acquisitions == 1
