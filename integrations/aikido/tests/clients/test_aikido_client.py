import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import Request, Response, HTTPStatusError
from clients.aikido_client import AikidoClient
from helpers.exceptions import MissingIntegrationCredentialException


@pytest.fixture
def aikido_client() -> AikidoClient:
    client = AikidoClient(
        base_url="https://api.example.com",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    client.auth = MagicMock()
    client.auth.get_token = AsyncMock(return_value="test_token")
    return client


@pytest.mark.asyncio
async def test_init_missing_credentials() -> None:
    with pytest.raises(MissingIntegrationCredentialException):
        AikidoClient(base_url="", client_id="", client_secret="")


@pytest.mark.asyncio
async def test_send_api_request_success(aikido_client: AikidoClient) -> None:
    test_data = {"key": "value"}
    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await aikido_client._send_api_request("test_endpoint")

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_404(aikido_client: AikidoClient) -> None:
    sample_req = Request("GET", "https://api.example.com/not_found")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "404", request=sample_req, response=mock_response
    )

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await aikido_client._send_api_request("not_found")
        assert result == {}


@pytest.mark.asyncio
async def test_send_api_request_with_post_method(aikido_client: AikidoClient) -> None:
    test_data = {"result": "success"}
    json_payload = {"key": "value"}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await aikido_client._send_api_request(
            "test_endpoint", method="POST", json_data=json_payload
        )

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_with_params(aikido_client: AikidoClient) -> None:
    test_data = {"result": "success"}
    params = {"page": 1, "per_page": 50}

    mock_response = MagicMock(spec=Response)
    mock_response.json.return_value = test_data
    mock_response.raise_for_status.return_value = None

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        result = await aikido_client._send_api_request("test_endpoint", params=params)

        assert result == test_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_send_api_request_unexpected_exception(
    aikido_client: AikidoClient,
) -> None:
    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = Exception("Unexpected error")

        with pytest.raises(Exception, match="Unexpected error"):
            await aikido_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_send_api_request_non_404_http_error(aikido_client: AikidoClient) -> None:
    sample_req = Request("GET", "https://api.example.com/error")
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = HTTPStatusError(
        "500 Internal Server Error", request=sample_req, response=mock_response
    )

    with patch.object(
        aikido_client.http_client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError):
            await aikido_client._send_api_request("test_endpoint")


@pytest.mark.asyncio
async def test_init_strips_trailing_slash_from_base_url() -> None:
    client = AikidoClient(
        base_url="https://api.example.com/",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    assert client.base_url == "https://api.example.com"
