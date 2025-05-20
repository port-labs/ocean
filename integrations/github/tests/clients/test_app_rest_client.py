import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import jwt

from port_ocean.utils import http_async_client

from github.clients.app_client import GithubAppRestClient
from github.clients.rest_client import GithubRestClient


@pytest.mark.asyncio
class TestGithubAppRestClient:
    @pytest.fixture
    def app_client(self) -> GithubAppRestClient:
        """Fixture to create a GithubAppRestClient instance."""
        return GithubAppRestClient(
            organization="test-org",
            github_host="https://api.github.com",
            app_id="test-app-id",
            private_key="test-private-key",
        )

    async def test_set_up_generates_and_sets_token(
        self, app_client: GithubAppRestClient
    ) -> None:
        """Test that set_up correctly generates and sets the installation token."""
        mock_install_id = 12345
        mock_install_token = "mock-installation-token"

        with (
            patch.object(
                app_client,
                "_get_installation_id",
                AsyncMock(return_value=mock_install_id),
            ) as mock_get_install_id,
            patch.object(
                app_client,
                "_get_installation_token",
                AsyncMock(return_value=mock_install_token),
            ) as mock_get_install_token,
            patch.object(
                GithubRestClient,
                "__init__",
                return_value=None,  # Mock the superclass init
            ) as mock_rest_client_init,
        ):
            await app_client.set_up()

            # Verify that the necessary internal methods were called
            mock_get_install_id.assert_called_once()
            mock_get_install_token.assert_called_once()

            # Verify that the superclass (GithubRestClient) was initialized with the correct token
            mock_rest_client_init.assert_called_once_with(
                mock_install_token, app_client.organization, app_client.github_host
            )

    async def test_send_api_request_regenerates_token_on_401(
        self, app_client: GithubAppRestClient
    ) -> None:
        """Test that token is regenerated and request retried on a 401 error."""
        initial_token = "initial-expired-token"
        new_token = "new-valid-token"
        app_client.token = initial_token  # Manually set an initial token

        # Create a mock response for the initial 401 error
        mock_401_response = MagicMock(spec=httpx.Response)
        mock_401_response.status_code = 401
        mock_401_response.text = "Unauthorized"
        # Simulate the httpx.HTTPStatusError for the 401
        http_401_error = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_401_response
        )
        mock_401_response.raise_for_status.side_effect = http_401_error

        # Create a mock response for the successful retry
        mock_success_response = MagicMock(spec=httpx.Response)
        mock_success_response.status_code = 200
        mock_success_response.json.return_value = {"data": "success"}

        # Use side_effect to make the first call fail with 401 and the second succeed
        mock_super_send_api = AsyncMock(
            side_effect=[http_401_error, mock_success_response]
        )

        with (
            patch.object(
                GithubRestClient,
                "send_api_request",
                mock_super_send_api,  # Mock the superclass method
            ),
            patch.object(
                app_client, "_get_installation_token", AsyncMock(return_value=new_token)
            ) as mock_get_install_token,
            patch(
                "github.clients.app_client.jwt.encode", spec=jwt.encode
            ) as mock_jwt_encode,
            patch.object(
                http_async_client,
                "get",
                spec=http_async_client.get,
            ) as mock_get,
        ):
            endpoint = "some/api/endpoint"
            method = "GET"
            params = {"key": "value"}
            mock_jwt_encode.return_value = "testjwt"

            get_response = MagicMock(spec=httpx.Response)
            mock_get.return_value = get_response
            get_response.raise_for_status = MagicMock()

            response = await app_client.send_api_request(
                endpoint, method=method, params=params
            )

            # Verify that _get_installation_token was called to get a new token
            mock_get_install_token.assert_called_once()
            mock_jwt_encode.assert_called()

            # Verify that the token on the client instance was updated
            assert app_client.token == new_token

            # Verify that the superclass send_api_request was called twice
            # First call with the initial token (implicitly via the mock)
            # Second call with the new token (implicitly via the mock's side_effect)
            assert mock_super_send_api.call_count == 2

            # Verify the response is from the successful retry
            assert response == mock_success_response
            assert response.status_code == 200
