from unittest.mock import AsyncMock, patch

import httpx
import pytest

from azure_devops.client.rate_limiter import (
    ADO_RATE_LIMIT_WINDOW_SECONDS,
    AzureDevOpsRateLimiter,
)
from azure_devops.client.retry_transport import AzureDevOpsRetryTransport
from port_ocean.helpers.retry import RetryConfig


def _make_transport(
    rate_limiter: AzureDevOpsRateLimiter | None = None,
    auth_header_refresher: AsyncMock | None = None,
) -> AzureDevOpsRetryTransport:
    wrapped = httpx.MockTransport(lambda request: httpx.Response(200, request=request))
    return AzureDevOpsRetryTransport(
        wrapped_transport=wrapped,
        rate_limiter=rate_limiter,
        auth_header_refresher=auth_header_refresher,
    )


class TestAzureDevOpsRetryTransport:
    @pytest.mark.asyncio
    async def test_after_retry_async_signals_shared_throttle_on_429(self) -> None:
        rate_limiter = AzureDevOpsRateLimiter()
        transport = _make_transport(rate_limiter=rate_limiter)
        request = httpx.Request("GET", "https://dev.azure.com/org/_apis/projects")
        response = httpx.Response(
            429,
            request=request,
            headers={
                "x-ratelimit-limit": "200",
                "x-ratelimit-remaining": "0",
                "x-ratelimit-reset": "1300",
            },
        )

        with patch("time.time", return_value=1000.0):
            await transport.after_retry_async(request, response, attempt=1)

        assert rate_limiter._throttle_until == 1000.0 + ADO_RATE_LIMIT_WINDOW_SECONDS
        assert rate_limiter._limit == 200
        assert rate_limiter._remaining == 0
        assert rate_limiter._reset_time == 1300.0

    def test_429_sleep_uses_fixed_ado_cooldown(self) -> None:
        transport = _make_transport()

        sleep = transport._calculate_sleep(
            attempts_made=1,
            headers=httpx.Headers({"retry-after": "1"}),
            status_code=429,
        )

        assert sleep == ADO_RATE_LIMIT_WINDOW_SECONDS

    def test_transport_error_sleep_uses_fixed_ado_cooldown(self) -> None:
        transport = _make_transport()

        sleep = transport._calculate_sleep(
            attempts_made=1,
            headers=httpx.Headers({}),
            status_code=None,
        )

        assert sleep == ADO_RATE_LIMIT_WINDOW_SECONDS

    @pytest.mark.asyncio
    async def test_before_retry_async_signals_shared_throttle_on_transport_retry(
        self,
    ) -> None:
        rate_limiter = AzureDevOpsRateLimiter()
        transport = _make_transport(rate_limiter=rate_limiter)
        request = httpx.Request("GET", "https://dev.azure.com/org/_apis/projects")

        with patch("time.time", return_value=1000.0):
            refreshed = await transport.before_retry_async(
                request,
                response=None,
                sleep_time=ADO_RATE_LIMIT_WINDOW_SECONDS,
                attempt=1,
            )

        assert refreshed is None
        assert rate_limiter._throttle_until == 1000.0 + ADO_RATE_LIMIT_WINDOW_SECONDS

    @pytest.mark.asyncio
    async def test_before_retry_async_refreshes_auth_headers(self) -> None:
        auth_header_refresher = AsyncMock(
            return_value={"Authorization": "Bearer fresh-token"}
        )
        transport = _make_transport(auth_header_refresher=auth_header_refresher)
        request = httpx.Request(
            "POST",
            "https://dev.azure.com/org/_apis/test",
            headers={
                "Authorization": "Bearer stale-token",
                "Accept": "application/json",
            },
            json={"hello": "world"},
        )

        refreshed = await transport.before_retry_async(
            request,
            response=None,
            sleep_time=ADO_RATE_LIMIT_WINDOW_SECONDS,
            attempt=1,
        )

        assert refreshed is not None
        assert refreshed.headers["authorization"] == "Bearer fresh-token"
        assert refreshed.headers["accept"] == "application/json"
        assert refreshed.content == request.content

    @pytest.mark.asyncio
    async def test_handle_async_request_retries_429_after_cooldown(self) -> None:
        requests_seen: list[httpx.Request] = []
        auth_header_refresher = AsyncMock(
            return_value={"Authorization": "Bearer fresh-token"}
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            requests_seen.append(request)
            if len(requests_seen) == 1:
                return httpx.Response(429, request=request)
            return httpx.Response(200, request=request, json={"ok": True})

        transport = AzureDevOpsRetryTransport(
            wrapped_transport=httpx.MockTransport(handler),
            auth_header_refresher=auth_header_refresher,
            retry_config=RetryConfig(
                max_attempts=10,
                base_delay=ADO_RATE_LIMIT_WINDOW_SECONDS,
                max_backoff_wait=ADO_RATE_LIMIT_WINDOW_SECONDS,
            ),
        )

        with patch(
            "port_ocean.helpers.retry.asyncio.sleep", new_callable=AsyncMock
        ) as sleep:
            response = await transport.handle_async_request(
                httpx.Request(
                    "GET",
                    "https://dev.azure.com/org/_apis/projects",
                    headers={"Authorization": "Bearer stale-token"},
                )
            )

        assert response.status_code == 200
        assert len(requests_seen) == 2
        assert requests_seen[1].headers["authorization"] == "Bearer fresh-token"
        sleep.assert_awaited_once_with(ADO_RATE_LIMIT_WINDOW_SECONDS)

    @pytest.mark.asyncio
    async def test_handle_async_request_retries_timeout_after_shared_cooldown(
        self,
    ) -> None:
        requests_seen: list[httpx.Request] = []
        rate_limiter = AzureDevOpsRateLimiter()

        async def handler(request: httpx.Request) -> httpx.Response:
            requests_seen.append(request)
            if len(requests_seen) == 1:
                raise httpx.ReadTimeout("ADO throttled the request")
            return httpx.Response(200, request=request, json={"ok": True})

        transport = AzureDevOpsRetryTransport(
            wrapped_transport=httpx.MockTransport(handler),
            rate_limiter=rate_limiter,
            retry_config=RetryConfig(
                max_attempts=10,
                base_delay=ADO_RATE_LIMIT_WINDOW_SECONDS,
                max_backoff_wait=ADO_RATE_LIMIT_WINDOW_SECONDS,
            ),
        )

        with (
            patch("time.time", return_value=1000.0),
            patch(
                "port_ocean.helpers.retry.asyncio.sleep", new_callable=AsyncMock
            ) as sleep,
        ):
            response = await transport.handle_async_request(
                httpx.Request("GET", "https://dev.azure.com/org/_apis/projects")
            )

        assert response.status_code == 200
        assert len(requests_seen) == 2
        assert rate_limiter._throttle_until == 1000.0 + ADO_RATE_LIMIT_WINDOW_SECONDS
        sleep.assert_awaited_once_with(ADO_RATE_LIMIT_WINDOW_SECONDS)
