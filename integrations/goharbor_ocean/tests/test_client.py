from unittest.mock import patch, Mock, AsyncMock
import asyncio
import pytest
from httpx import Response, Request, HTTPStatusError

from harbor.client import HarborClient
from harbor.constants import DEFAULT_TIMEOUT, DEFAULT_MAX_CONCURRENT_REQUESTS
from harbor.exceptions import (
    HarborAPIError,
    ServerError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    InvalidConfigurationError,
    MissingCredentialsError,
    RateLimitError,
)
from tests.fixtures import (
    harbor_client,
    mock_async_client,
    mock_project_response,
    mock_user_response,
    mock_repository_response,
    mock_artifact_response,
)


class TestHarborClientInitialization:

    def test_init_success_with_valid_attributes(self, harbor_config):
        client = HarborClient(**harbor_config, verify_ssl=False)

        assert client.base_url == harbor_config["base_url"]
        assert client.username == harbor_config["username"]
        assert client.password == harbor_config["password"]
        assert client.verify_ssl is False
        assert client.client is not None
        assert client._semaphore is not None

    def test_strips_trailing_slash_base_url(self, harbor_config):
        harbor_config["base_url"] = "https://harbor.onmypc.com/api/v2.0/"

        client = HarborClient(**harbor_config, verify_ssl=False)
        assert client.base_url == "https://harbor.onmypc.com"

    def test_empty_base_url_raises_invalid_configuration_error(self):
        with pytest.raises(InvalidConfigurationError):
            HarborClient(base_url="", username="user", password="pass")

    def test_missing_username_raises_credentials_configuration_error(self):
        with pytest.raises(MissingCredentialsError):
            HarborClient(
                base_url="https://harbor.onmypc.com", username="", password="pass"
            )

    def test_missing_pass_raises_credentials_configuration_error(self):
        with pytest.raises(MissingCredentialsError):
            HarborClient(
                base_url="https://harbor.onmypc.com", username="user", password=""
            )


    def test_null_credentials_raises_credentials_configuration_error(self):
        with pytest.raises(MissingCredentialsError):
            HarborClient(
                base_url="https://harbor.onmypc.com", username=None, password="pass"
            )

class TestSendAPIRequest:
    """ Tests for the _send_api_request method of HarborClient."""

    @pytest.mark.asyncio
    async def test_can_make_successful_get_request(
        self, harbor_client_mocked, mock_async_client, mock_http_response
    ):
        # test that we can make a successful GET request
        mock_async_client.request.return_value = mock_http_response(
                status_code=200, json_data={"success": True}
        )

        result = await harbor_client_mocked._send_api_request("GET", "/projects")

        assert result == {"success": True}
        mock_async_client.request.assert_called_once()


    @pytest.mark.asyncio
    async def test_can_include_query_params_in_request(self, harbor_client_mocked, mock_async_client, mock_http_response):
        # test that we are able to correctly pass in query params
        # in the request
        mock_async_client.request.return_value = mock_http_response(
                status_code=200, json_data=[]
        )

        await harbor_client_mocked._send_api_request(
            "GET", "/projects", params={"page": 1, "page_size": 10}
        )

        call_kwargs = mock_async_client.request.call_args.kwargs
        assert "params" in call_kwargs
        assert call_kwargs["params"]["page"] == 1
        assert call_kwargs["params"]["page_size"] == 10

    @pytest.mark.asyncio
    async def test_handles_unauthorized_error(self, harbor_client_mocked, mock_async_client, mock_http_error):
        # should raise UnauthorizedError for 401 responses
        mock_async_client.request.side_effect = mock_http_error(401, "Unauthorized")

        with pytest.raises(UnauthorizedError):
            await harbor_client_mocked._send_api_request("GET", "/projects")


    @pytest.mark.asyncio
    async def test_handles_forbidden_error(
        self, harbor_client_mocked, mock_async_client, mock_http_error
    ):
        # should raise ForbiddenError for 403 responses
        mock_async_client.request.side_effect = mock_http_error(403, "Forbidden")

        with pytest.raises(ForbiddenError):
            await harbor_client_mocked._send_api_request("GET", "/users")

    @pytest.mark.asyncio
    async def test_handles_not_found_error(
        self, harbor_client_mocked, mock_async_client, mock_http_error
    ):
        # should raise NotFoundError for 404 responses
        mock_async_client.request.side_effect = mock_http_error(404, "Not Found")

        with pytest.raises(NotFoundError):
            await harbor_client_mocked._send_api_request("GET", "/projects/nonexistent")

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(
            self, harbor_client_mocked, mock_async_client, mock_http_error, mock_http_response
    ):
        # should retry on 429 responses and eventually succeed
        rate_limit_error = mock_http_error(429, "Rate Limit Exceeded")
        rate_limit_error.response.headers = {"Retry-After": "1"}

        success_response = mock_http_response(status_code=200, json_data={"success": True})
        mock_async_client.request.side_effect = [rate_limit_error, success_response]

        with patch('asyncio.sleep', return_value=None) as mock_sleep:
            result = await harbor_client_mocked._send_api_request("GET", "/projects")

            assert result == {"success": True}
            mock_sleep.assert_called_once_with(1)
            assert mock_async_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_server_error(
        self, harbor_client_mocked, mock_async_client, mock_http_error
    ):
        # should gracefuly handle server errors
        mock_async_client.request.side_effect = mock_http_error(500, 'Server Error')

        with pytest.raises(ServerError):
            await harbor_client_mocked._send_api_request("GET", "/projects")
