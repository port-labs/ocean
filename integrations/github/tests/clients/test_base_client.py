from typing import Any, AsyncGenerator, Optional
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.http.base_client import AbstractGithubClient


# Create a concrete implementation of the abstract class for testing
class ConcreteGithubClient(AbstractGithubClient):
    @property
    def base_url(self) -> str:
        return "https://api.github.com"

    async def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        # Need to yield something to make it a valid generator
        if (
            False
        ):  # This ensures the method has the correct signature but never actually yields
            yield []
        return  # Explicitly return to end the generator


@pytest.mark.asyncio
class TestAbstractGithubClient:
    async def test_send_api_request_success(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        # Test successful API request
        client = ConcreteGithubClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "name": "test-repo"}

        with patch(
            "port_ocean.utils.http_async_client.request",
            AsyncMock(return_value=mock_response),
        ):
            response = await client.send_api_request("repos/test-org/test-repo")

            assert response == mock_response.json()

    async def test_send_api_request_with_params_and_json(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        # Test API request with query parameters and JSON body
        client = ConcreteGithubClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        params = {"type": "public"}
        json_data = {"name": "new-repo", "private": False}
        url = "https://api.github.com/orgs/test-org/repos"

        with patch(
            "port_ocean.utils.http_async_client.request",
            AsyncMock(return_value=mock_response),
        ) as mock_request:
            await client.send_api_request(
                url, method="POST", params=params, json_data=json_data
            )

            # Verify the request was made with the correct arguments
            mock_request.assert_called_once_with(
                method="POST",
                url=url,
                params=params,
                json=json_data,
                headers=await client.headers,
            )

    async def test_send_api_request_404_error(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        # Test 404 Not Found error handling
        client = ConcreteGithubClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch(
            "port_ocean.utils.http_async_client.request",
            AsyncMock(return_value=mock_response),
        ):
            # Should return the response instead of raising for 404
            response = await client.send_api_request("repos/test-org/nonexistent-repo")
            assert response == {}

    async def test_send_api_request_403_error(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        # Test other HTTP error (e.g., 403 Forbidden)
        client = ConcreteGithubClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        http_error = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = http_error

        with patch(
            "port_ocean.utils.http_async_client.request",
            AsyncMock(return_value=mock_response),
        ):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.send_api_request("orgs/forbidden-org/repos")

            assert exc_info.value.response.status_code == 403

    async def test_send_api_request_network_error(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        # Test network-level HTTP error
        client = ConcreteGithubClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Create a network error
        network_error = httpx.ConnectError("Connection failed")

        with patch(
            "port_ocean.utils.http_async_client.request",
            AsyncMock(side_effect=network_error),
        ):
            with pytest.raises(httpx.HTTPError):
                await client.send_api_request("orgs/test-org/repos")

    async def test_send_api_request_different_http_methods(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        # Test different HTTP methods
        client = ConcreteGithubClient(
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        url = "https://api.github.com/repos/test-org/test-repo"

        with patch(
            "port_ocean.utils.http_async_client.request",
            AsyncMock(return_value=mock_response),
        ) as mock_request:
            # Test GET (default)
            await client.send_api_request(url)
            mock_request.assert_called_with(
                method="GET",
                url=url,
                params=None,
                json=None,
                headers=await client.headers,
            )

            # Test POST
            mock_request.reset_mock()
            await client.send_api_request(url, method="POST")
            mock_request.assert_called_with(
                method="POST",
                url=url,
                params=None,
                json=None,
                headers=await client.headers,
            )

            # Test PUT
            mock_request.reset_mock()
            await client.send_api_request(url, method="PUT")
            mock_request.assert_called_with(
                method="PUT",
                url=url,
                params=None,
                json=None,
                headers=await client.headers,
            )

            # Test PATCH
            mock_request.reset_mock()
            await client.send_api_request(url, method="PATCH")
            mock_request.assert_called_with(
                method="PATCH",
                url=url,
                params=None,
                json=None,
                headers=await client.headers,
            )

            # Test DELETE
            mock_request.reset_mock()
            await client.send_api_request(url, method="DELETE")
            mock_request.assert_called_with(
                method="DELETE",
                url=url,
                params=None,
                json=None,
                headers=await client.headers,
            )
