from types import SimpleNamespace, TracebackType
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from port_ocean.rate_limiting.models import CentralizedRateLimitState
from port_ocean.rate_limiting.rate_limit_wrapper import RateLimitWrapper
from port_ocean.rate_limiting.utils import use_centralized_rate_limiting


class _StubWrapper(RateLimitWrapper):
    def __init__(self) -> None:
        super().__init__("test-pool")
        self.local_acquire = AsyncMock()
        self.local_release = AsyncMock()
        self.local_ingest = AsyncMock()

    async def _local_acquire(self) -> None:
        await self.local_acquire()

    async def _notify_transport_rate_limit_retry(
        self, response: httpx.Response
    ) -> None:
        pass

    async def _local_release(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.local_release()

    async def _local_ingest_response(
        self, response: httpx.Response, context: str
    ) -> None:
        await self.local_ingest(response, context)

    def _parse_centralized_state(
        self, response: httpx.Response, context: str
    ) -> CentralizedRateLimitState | None:
        return CentralizedRateLimitState(remaining=1, limit=100, reset_at=1.0)

    def _centralized_is_rate_limited(self, response: httpx.Response) -> bool:
        return False

    def _local_is_close_to_rate_limit(self) -> bool:
        return True

    def _local_seconds_until_rate_limit_reset(self) -> float:
        return 42.0


@pytest.mark.asyncio
async def test_local_acquire_when_centralized_inactive() -> None:
    wrapper = _StubWrapper()
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
        return_value=False,
    ):
        async with wrapper:
            pass
    wrapper.local_acquire.assert_awaited_once()
    wrapper.local_release.assert_awaited_once()


@pytest.mark.asyncio
async def test_acquire_calls_centralized_admission() -> None:
    wrapper = _StubWrapper()
    with (
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.await_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as await_acquire,
    ):
        await wrapper.acquire()
    await_acquire.assert_awaited_once_with("test-pool")


@pytest.mark.asyncio
async def test_skips_local_acquire_when_centralized_active() -> None:
    wrapper = _StubWrapper()
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
        return_value=True,
    ):
        async with wrapper:
            pass
    wrapper.local_acquire.assert_not_awaited()
    wrapper.local_release.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_rate_limit_response_skips_local_on_transport_retry() -> None:
    wrapper = _StubWrapper()
    response = httpx.Response(200)
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
        return_value=False,
    ):
        await wrapper.record_rate_limit_response(response)
    wrapper.local_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_rate_limit_response_uses_local_with_resource_context() -> None:
    wrapper = _StubWrapper()
    response = httpx.Response(200)
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
        return_value=False,
    ):
        await wrapper.record_rate_limit_response(response, context="/repos")
    wrapper.local_ingest.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_rate_limit_response_publishes_when_centralized() -> None:
    wrapper = _StubWrapper()
    response = httpx.Response(200)
    with (
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
            return_value=True,
        ),
        patch(
            "port_ocean.rate_limiting.rate_limit_wrapper.record_centralized_rate_limit",
            new_callable=AsyncMock,
        ) as record,
    ):
        await wrapper.record_rate_limit_response(response, context="x")
    record.assert_awaited_once()
    wrapper.local_ingest.assert_not_awaited()


def test_quota_methods_noop_when_centralized() -> None:
    wrapper = _StubWrapper()
    with patch(
        "port_ocean.rate_limiting.rate_limit_wrapper.use_centralized_rate_limiting",
        return_value=True,
    ):
        assert wrapper.is_close_to_rate_limit() is False
        assert wrapper.seconds_until_rate_limit_reset() == 0.0


def test_use_centralized_requires_active_limiter() -> None:
    app = SimpleNamespace(
        config=SimpleNamespace(
            centralized_rate_limiter=SimpleNamespace(enabled=True),
        ),
        centralized_rate_limiter=object(),
        initialized=True,
    )
    with patch("port_ocean.rate_limiting.utils.ocean", app):
        assert use_centralized_rate_limiting() is True
