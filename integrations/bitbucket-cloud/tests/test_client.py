import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from httpx import AsyncClient, HTTPStatusError
from port_ocean.context.event import event_context
from typing import Any, AsyncIterator, Generator
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.helpers.token_manager import TokenManager
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException


@pytest.fixture
def mock_http_client() -> AsyncClient:
    """Create a mock HTTP client."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def mock_integration_config() -> Generator[dict[str, str], None, None]:
    """Mock the ocean integration config."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
        "bitbucket_username": "test_user",
        "bitbucket_app_password": "test_password",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture
async def mock_client(
    mock_integration_config: dict[str, str], mock_http_client: AsyncClient
) -> BitbucketClient:
    """Create BitbucketClient using create_from_ocean_config."""
    with patch("bitbucket_cloud.client.http_async_client", mock_http_client):
        return BitbucketClient.create_from_ocean_config()


@pytest.mark.asyncio
async def test_client_init_with_token() -> None:
    """Test client initialization with token auth."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
        "bitbucket_workspace_token": "test_token",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        client = BitbucketClient.create_from_ocean_config()
        assert "Bearer test_token" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_with_app_password(
    mock_integration_config: dict[str, str]
) -> None:
    """Test client initialization with app password auth."""
    client = BitbucketClient.create_from_ocean_config()
    assert "Basic" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_no_auth() -> None:
    """Test client initialization with no auth raises error."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_host_url": "https://api.bitbucket.org/2.0",
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        with pytest.raises(MissingIntegrationCredentialException) as exc_info:
            BitbucketClient.create_from_ocean_config()
        assert (
            "Either workspace token or both username and app password must be provided"
            in str(exc_info.value)
        )


@pytest.mark.asyncio
async def test_send_api_request_success(mock_client: BitbucketClient) -> None:
    """Test successful API request."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    with patch.object(
        mock_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client._send_api_request(
            f"{mock_client.base_url}/test/endpoint"
        )
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params=None,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_with_params(mock_client: BitbucketClient) -> None:
    """Test API request with query parameters."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    params = {"page": 1, "pagelen": 100}
    with patch.object(
        mock_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_response
        result = await mock_client._send_api_request(
            f"{mock_client.base_url}/test/endpoint", params=params
        )
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params=params,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_error(mock_client: BitbucketClient) -> None:
    """Test API request with error response and error message extraction."""
    # Create a mock response with a 400 status code and error message
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error": {"message": "Test error message"}}

    original_error = HTTPStatusError(
        "400 Client Error", request=MagicMock(), response=mock_response
    )
    mock_response.raise_for_status.side_effect = original_error

    with (
        patch.object(
            mock_client.client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch("bitbucket_cloud.client.logger.error") as mock_logger,
    ):
        mock_request.return_value = mock_response

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_client._send_api_request(f"{mock_client.base_url}/test/endpoint")

        assert exc_info.value == original_error
        mock_logger.assert_called_once_with("Bitbucket API error: 400 Client Error")


@pytest.mark.asyncio
async def test_send_paginated_api_request(mock_client: BitbucketClient) -> None:
    """Test paginated API request."""
    page1 = {
        "values": [{"id": 1}, {"id": 2}],
        "next": "https://api.bitbucket.org/2.0/test/endpoint?page=2",
    }
    page2 = {"values": [{"id": 3}], "next": None}
    with patch.object(
        mock_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2]
        batches = []
        async for batch in mock_client._send_paginated_api_request(
            f"{mock_client.base_url}/test/endpoint"
        ):
            batches.append(batch)

        assert batches[0] == [{"id": 1}, {"id": 2}]
        assert batches[1] == [{"id": 3}]
        assert len(batches) == 2

        all_results = [item for batch in batches for item in batch]
        assert len(all_results) == 3
        assert [item["id"] for item in all_results] == [1, 2, 3]

        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_projects(mock_client: BitbucketClient) -> None:
    """Test getting projects."""
    mock_data = {"values": [{"key": "TEST", "name": "Test Project"}]}
    async with event_context("test_event"):
        with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for projects in mock_client.get_projects():
                assert projects == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/workspaces/test_workspace/projects"
            )


@pytest.mark.asyncio
async def test_get_repositories(mock_client: BitbucketClient) -> None:
    """Test getting repositories."""
    mock_data = {"values": [{"slug": "test-repo", "name": "Test Repo"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_fetch_paginated_api_with_rate_limiter"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for repos in mock_client.get_repositories():
                assert repos == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/test_workspace", params=None
            )


@pytest.mark.asyncio
async def test_get_directory_contents(mock_client: BitbucketClient) -> None:
    """Test getting directory contents."""
    mock_dir_data = {"values": [{"type": "commit_directory", "path": "src"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_fetch_paginated_api_with_rate_limiter"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_dir_data["values"]

            mock_paginated.return_value = mock_generator()
            async for contents in mock_client.get_directory_contents(
                "test-repo", "main", "", 2
            ):
                assert contents == mock_dir_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/{mock_client.workspace}/test-repo/src/main/",
                params={"max_depth": 2, "pagelen": 100},
            )


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client: BitbucketClient) -> None:
    """Test getting pull requests."""
    mock_data = {"values": [{"id": 1, "title": "Test PR"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_fetch_paginated_api_with_rate_limiter"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for prs in mock_client.get_pull_requests("test-repo"):
                assert prs == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/{mock_client.workspace}/test-repo/pullrequests",
                params={"state": "OPEN", "pagelen": 50},
            )


@pytest.mark.asyncio
async def test_client_init_with_multiple_tokens() -> None:
    """Test client initialization with multiple workspace tokens."""
    multiple_tokens = "token1,token2,token3"
    client = BitbucketClient(
        workspace="test_workspace",
        host="https://api.bitbucket.org/2.0",
        workspace_token=multiple_tokens,
    )

    assert client.token_manager is not None
    assert len(client.token_manager.tokens) == 3
    assert client.token_manager.tokens == ["token1", "token2", "token3"]
    assert client.token_manager.current_token == "token1"
    assert len(client.token_manager.rate_limiters) == 3

    # Check that headers are set correctly
    assert "Bearer token1" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_with_single_token_in_multiple_format() -> None:
    """Test client initialization with single token that has commas/spaces."""
    single_token = "  token1  "
    client = BitbucketClient(
        workspace="test_workspace",
        host="https://api.bitbucket.org/2.0",
        workspace_token=single_token,
    )

    # Should be treated as single token (no token manager)
    assert client.token_manager is None
    assert "Bearer token1" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_token_manager_rotation() -> None:
    """Test token manager rotation logic."""
    tokens = ["token1", "token2", "token3"]
    manager = TokenManager(tokens, 100, 100)

    assert manager.current_token == "token1"
    assert manager.current_index == 0

    manager._rotate_to_next_token()
    assert manager.current_token == "token2"
    assert manager.current_index == 1

    manager._rotate_to_next_token()
    assert manager.current_token == "token3"
    assert manager.current_index == 2

    # Should wrap around
    manager._rotate_to_next_token()
    assert manager.current_token == "token1"
    assert manager.current_index == 0


@pytest.mark.asyncio
async def test_fetch_with_token_rotation() -> None:
    """Test that fetch_paginated_api_with_rate_limiter works with token rotation."""
    # Create a client with multiple tokens
    client = BitbucketClient(
        workspace="test_workspace",
        host="https://api.bitbucket.org/2.0",
        workspace_token="token1,token2",
    )

    mock_data = {"values": [{"id": 1}, {"id": 2}], "next": None}

    async with event_context("test_event"):
        with (
            patch.object(
                client, "_send_api_request", new_callable=AsyncMock
            ) as mock_request,
            patch.object(
                client, "_update_authorization_header"
            ) as mock_update_header,
        ):
            mock_request.return_value = mock_data

            batches = []
            async for batch in client._fetch_paginated_api_with_rate_limiter(
                f"{client.base_url}/test/endpoint"
            ):
                batches.append(batch)

            assert len(batches) == 1
            assert batches[0] == [{"id": 1}, {"id": 2}]

            # Verify that authorization header was updated
            mock_update_header.assert_called_with("token1")


@pytest.mark.asyncio
async def test_update_authorization_header(mock_client: BitbucketClient) -> None:
    """Test that authorization header is updated correctly."""
    new_token = "new_test_token"

    # Patch the client.headers.update method specifically
    with patch.object(mock_client.client.headers, "update") as mock_update:
        mock_client._update_authorization_header(new_token)

        # Verify that the client's headers were updated correctly
        assert mock_client.headers["Authorization"] == f"Bearer {new_token}"

        # Verify that the update method was called on the mock http client
        mock_update.assert_called_with(mock_client.headers)


@pytest.mark.asyncio
async def test_token_rate_limiter_context_direct_usage() -> None:
    """Test that TokenRateLimiterContext can be used directly without wrapper method."""
    from bitbucket_cloud.helpers.token_manager import TokenRateLimiterContext

    tokens = ["token1", "token2", "token3"]
    manager = TokenManager(tokens, 100, 100)

    # Test direct instantiation and usage
    async with TokenRateLimiterContext(manager) as ctx:
        selected_token = ctx.get_token()
        assert selected_token in tokens
        assert isinstance(selected_token, str)
        assert len(selected_token) > 0

    # Verify context cleanup
    assert (
        ctx.selected_token == selected_token
    )  # Token should still be available after exit


@pytest.mark.asyncio
async def test_get_headers() -> None:
    """Test the authentication headers with different authentication types."""
    # Test bearer token headers
    client = BitbucketClient(
        workspace="test_workspace",
        host="https://api.bitbucket.org/2.0",
        workspace_token="test_token",
    )
    expected_bearer = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer test_token",
    }
    assert client.headers == expected_bearer

    # Test basic auth headers
    client = BitbucketClient(
        workspace="test_workspace",
        host="https://api.bitbucket.org/2.0",
        username="test_user",
        app_password="test_password",
    )
    # Basic auth headers should contain Authorization with Basic prefix
    assert "Authorization" in client.headers
    assert client.headers["Authorization"].startswith("Basic ")
    assert client.headers["Accept"] == "application/json"
    assert client.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_client_init_with_invalid_workspace_tokens() -> None:
    """Test that invalid workspace tokens raise appropriate exceptions."""
    from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException

    # Test with separators only
    with pytest.raises(
        MissingIntegrationCredentialException, match="No valid tokens found"
    ):
        BitbucketClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            workspace_token=",,,",
        )

    # Test with whitespace only
    with pytest.raises(
        MissingIntegrationCredentialException, match="No valid tokens found"
    ):
        BitbucketClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            workspace_token="   ",
        )

    # Test with mixed separators and whitespace
    with pytest.raises(
        MissingIntegrationCredentialException, match="No valid tokens found"
    ):
        BitbucketClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            workspace_token=" , , ,",
        )

    # Test with empty string (should hit the general auth error, not token validation)
    with pytest.raises(
        MissingIntegrationCredentialException,
        match="Either workspace token or both username and app password must be provided",
    ):
        BitbucketClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            workspace_token="",
        )
