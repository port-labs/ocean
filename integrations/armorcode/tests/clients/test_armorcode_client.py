import pytest
from unittest.mock import AsyncMock, patch
from httpx import Request, Response, HTTPStatusError
from armorcode.clients.http.armorcode_client import ArmorcodeClient


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
