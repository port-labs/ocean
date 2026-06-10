from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from port_ocean.clients.port.retry_transport import TokenRetryTransport
from port_ocean.helpers.retry import RetryConfig


@pytest.mark.asyncio
async def test_token_error_without_local_expiry() -> None:
    port_client = Mock()
    port_client.auth = Mock()
    port_client.auth.last_token_object = Mock(expired=False)

    transport = TokenRetryTransport(port_client=port_client, wrapped_transport=Mock())

    response = Mock(spec=httpx.Response)
    response.status_code = HTTPStatus.UNAUTHORIZED
    response.request = httpx.Request(
        "POST", "https://api.getport.io/v1/entities/search"
    )

    assert transport.is_token_error(response) is True


@pytest.mark.asyncio
async def test_before_retry_refreshes_token_on_unauthorized() -> None:
    port_client = Mock()
    port_client.auth = Mock()
    port_client.auth.last_token_object = Mock(expired=False)
    port_client.auth.refresh_token = AsyncMock(return_value="Bearer new-token")

    transport = TokenRetryTransport(
        port_client=port_client,
        wrapped_transport=Mock(),
        retry_config=RetryConfig(max_attempts=2),
    )

    request = httpx.Request(
        "POST",
        "https://api.getport.io/v1/entities/search",
        headers={"Authorization": "Bearer old-token"},
        content=b"{}",
        extensions={"retryable": True},
    )
    response = Mock(spec=httpx.Response)
    response.status_code = HTTPStatus.UNAUTHORIZED
    response.request = request

    refreshed_request = await transport.before_retry_async(
        request, response, sleep_time=1.0, attempt=1
    )

    assert refreshed_request is not None
    assert refreshed_request.headers["Authorization"] == "Bearer new-token"
    port_client.auth.refresh_token.assert_awaited_once()
