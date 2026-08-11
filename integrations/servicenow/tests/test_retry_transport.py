from unittest.mock import AsyncMock

import httpx
import pytest
from port_ocean.helpers.retry import RetryConfig

from retry_transport import ServiceNowRetryTransport


class TestServiceNowRetryTransport:
    @pytest.mark.asyncio
    async def test_retry_uses_auth_headers_from_refresher_after_retry_sleep(
        self,
    ) -> None:
        request_auth_headers: list[str | None] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            request_auth_headers.append(request.headers.get("Authorization"))
            if len(request_auth_headers) == 1:
                return httpx.Response(httpx.codes.TOO_MANY_REQUESTS)
            return httpx.Response(httpx.codes.OK)

        auth_header_refresher = AsyncMock(
            return_value={"Authorization": "Bearer fresh-token"}
        )
        transport = ServiceNowRetryTransport(
            wrapped_transport=httpx.MockTransport(handler),
            retry_config=RetryConfig(max_attempts=1, base_delay=0, jitter_ratio=0),
            auth_header_refresher=auth_header_refresher,
        )

        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get(
                "https://test-instance.service-now.com/api/now/table/incident",
                headers={"Authorization": "Bearer stale-token"},
            )

        assert response.status_code == httpx.codes.OK
        assert request_auth_headers == ["Bearer stale-token", "Bearer fresh-token"]
        auth_header_refresher.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unauthorized_retry_uses_auth_headers_from_refresher(
        self,
    ) -> None:
        request_auth_headers: list[str | None] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            request_auth_headers.append(request.headers.get("Authorization"))
            if len(request_auth_headers) == 1:
                return httpx.Response(httpx.codes.UNAUTHORIZED)
            return httpx.Response(httpx.codes.OK)

        auth_header_refresher = AsyncMock(
            return_value={"Authorization": "Bearer fresh-token"}
        )
        transport = ServiceNowRetryTransport(
            wrapped_transport=httpx.MockTransport(handler),
            retry_config=RetryConfig(max_attempts=1, base_delay=0, jitter_ratio=0),
            auth_header_refresher=auth_header_refresher,
        )

        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.get(
                "https://test-instance.service-now.com/api/now/table/incident",
                headers={"Authorization": "Bearer stale-token"},
            )

        assert response.status_code == httpx.codes.OK
        assert request_auth_headers == ["Bearer stale-token", "Bearer fresh-token"]
        auth_header_refresher.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_before_retry_after_sleep_uses_auth_headers_from_refresher(
        self,
    ) -> None:
        auth_header_refresher = AsyncMock(
            return_value={"Authorization": "Bearer fresh-token"}
        )
        transport = ServiceNowRetryTransport(
            wrapped_transport=httpx.MockTransport(
                lambda request: httpx.Response(httpx.codes.OK)
            ),
            auth_header_refresher=auth_header_refresher,
        )
        request = httpx.Request(
            "GET",
            "https://test-instance.service-now.com/api/now/table/incident",
            headers={"Authorization": "Bearer stale-token"},
        )

        retry_request = await transport.before_retry_after_sleep_async(
            request=request,
            response=httpx.Response(httpx.codes.TOO_MANY_REQUESTS),
            sleep_time=60,
            attempt=1,
        )

        assert retry_request is not None
        assert retry_request.headers["Authorization"] == "Bearer fresh-token"
        auth_header_refresher.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_before_retry_after_sleep_returns_none_without_refresher(
        self,
    ) -> None:
        transport = ServiceNowRetryTransport(
            wrapped_transport=httpx.MockTransport(
                lambda request: httpx.Response(httpx.codes.OK)
            ),
        )
        request = httpx.Request(
            "GET",
            "https://test-instance.service-now.com/api/now/table/incident",
        )

        retry_request = await transport.before_retry_after_sleep_async(
            request=request,
            response=None,
            sleep_time=60,
            attempt=1,
        )

        assert retry_request is None
