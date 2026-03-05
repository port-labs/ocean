import pytest
from typing import Any
from unittest.mock import AsyncMock, patch
from httpx import Request, Response, HTTPStatusError
from aiolimiter import AsyncLimiter
from armorcode.clients.http.armorcode_client import ArmorcodeClient
from armorcode.clients.http.base_client import ARMORCODE_REQUESTS_PER_MINUTE


@pytest.fixture
def armorcode_client() -> ArmorcodeClient:
    from armorcode.clients.auth.api_key_authenticator import ApiKeyAuthenticator

    authenticator = ApiKeyAuthenticator("test_api_key")
    client = ArmorcodeClient(
        base_url="https://app.armorcode.com",
        authenticator=authenticator,
    )
    return client


@pytest.mark.asyncio
async def test_init_strips_trailing_slash_from_base_url() -> None:
    from armorcode.clients.auth.api_key_authenticator import ApiKeyAuthenticator

    authenticator = ApiKeyAuthenticator("test_api_key")
    client = ArmorcodeClient(
        base_url="https://app.armorcode.com/",
        authenticator=authenticator,
    )
    assert client.base_url == "https://app.armorcode.com"


@pytest.mark.asyncio
async def test_client_has_rate_limiter_with_correct_config(
    armorcode_client: ArmorcodeClient,
) -> None:
    assert isinstance(armorcode_client._rate_limiter, AsyncLimiter)
    assert armorcode_client._rate_limiter.max_rate == ARMORCODE_REQUESTS_PER_MINUTE
    assert armorcode_client._rate_limiter.time_period == 60


@pytest.mark.asyncio
async def test_client_retry_config_includes_post(
    armorcode_client: ArmorcodeClient,
) -> None:
    transport = armorcode_client.http_client._transport
    for attr in ("_wrapped", "wrapped"):
        while hasattr(transport, attr):
            transport = getattr(transport, attr)
    assert "POST" not in transport._retry_config.retryable_methods


@pytest.mark.asyncio
async def test_post_request_sent_with_retryable_extension(
    armorcode_client: ArmorcodeClient,
) -> None:
    test_data = {"key": "value"}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("POST", "https://app.armorcode.com/api/findings"),
    )
    captured_extensions: list[dict[str, Any]] = []

    async def capturing_request(**kwargs: Any) -> Response:
        captured_extensions.append(kwargs.get("extensions", {}))
        return mock_response

    with patch.object(
        armorcode_client.http_client,
        "request",
        side_effect=capturing_request,
    ):
        await armorcode_client.send_api_request(
            "/api/findings", method="POST", json_data={}, retry=True
        )

    assert captured_extensions[0].get("retryable") is True


@pytest.mark.asyncio
async def test_get_request_not_sent_with_retryable_extension(
    armorcode_client: ArmorcodeClient,
) -> None:
    test_data = {"content": [], "last": True}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("GET", "https://app.armorcode.com/user/product"),
    )
    captured_extensions: list[dict[str, Any]] = []

    async def capturing_request(**kwargs: Any) -> Response:
        captured_extensions.append(kwargs.get("extensions", {}))
        return mock_response

    with patch.object(
        armorcode_client.http_client,
        "request",
        side_effect=capturing_request,
    ):
        await armorcode_client.send_api_request("/user/product", method="GET")

    assert not captured_extensions[0].get("retryable")


@pytest.mark.asyncio
async def test_post_without_retry_flag_not_sent_with_retryable_extension(
    armorcode_client: ArmorcodeClient,
) -> None:
    test_data = {"key": "value"}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("POST", "https://app.armorcode.com/some/other/endpoint"),
    )
    captured_extensions: list[dict[str, Any]] = []

    async def capturing_request(**kwargs: Any) -> Response:
        captured_extensions.append(kwargs.get("extensions", {}))
        return mock_response

    with patch.object(
        armorcode_client.http_client,
        "request",
        side_effect=capturing_request,
    ):
        await armorcode_client.send_api_request(
            "/some/other/endpoint", method="POST", json_data={}
        )

    assert not captured_extensions[0].get("retryable")


@pytest.mark.asyncio
async def test_send_api_request_success(armorcode_client: ArmorcodeClient) -> None:
    test_data = {"key": "value"}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("GET", "https://app.armorcode.com/test"),
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await armorcode_client.send_api_request("/test")

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_404(armorcode_client: ArmorcodeClient) -> None:
    mock_response = Response(
        status_code=404,
        request=Request("GET", "https://app.armorcode.com/test"),
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await armorcode_client.send_api_request("/test")

        assert result == {}


@pytest.mark.asyncio
async def test_send_api_request_non_404_http_error(
    armorcode_client: ArmorcodeClient,
) -> None:
    mock_response = Response(
        status_code=500,
        request=Request("GET", "https://app.armorcode.com/test"),
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await armorcode_client.send_api_request("/test")


@pytest.mark.asyncio
async def test_send_api_request_with_params(armorcode_client: ArmorcodeClient) -> None:
    test_data = {"key": "value"}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("GET", "https://app.armorcode.com/test"),
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        params = {"param1": "value1"}
        await armorcode_client.send_api_request("/test", params=params)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[1]["params"]["param1"] == "value1"


@pytest.mark.asyncio
async def test_send_api_request_with_post_method(
    armorcode_client: ArmorcodeClient,
) -> None:
    test_data = {"key": "value"}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("POST", "https://app.armorcode.com/test"),
    )

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        json_data = {"data": "test"}
        await armorcode_client.send_api_request(
            "/test", method="POST", json_data=json_data
        )

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["json"] == json_data


@pytest.mark.asyncio
async def test_send_api_request_unexpected_exception(
    armorcode_client: ArmorcodeClient,
) -> None:
    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("Unexpected error")

        with pytest.raises(Exception, match="Unexpected error"):
            await armorcode_client.send_api_request("/test")


@pytest.mark.asyncio
async def test_send_api_request_acquires_rate_limiter(
    armorcode_client: ArmorcodeClient,
) -> None:
    test_data = {"key": "value"}
    mock_response = Response(
        status_code=200,
        json=test_data,
        request=Request("POST", "https://app.armorcode.com/findings"),
    )

    acquired: list[bool] = []

    class TrackingLimiter(AsyncLimiter):
        async def __aenter__(self) -> "TrackingLimiter":
            acquired.append(True)
            return await super().__aenter__()  # type: ignore[return-value]

    armorcode_client._rate_limiter = TrackingLimiter(ARMORCODE_REQUESTS_PER_MINUTE, 60)

    with patch.object(
        armorcode_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        await armorcode_client.send_api_request(
            "/findings", method="POST", json_data={}
        )

    assert acquired, "Rate limiter was not acquired during send_api_request"

