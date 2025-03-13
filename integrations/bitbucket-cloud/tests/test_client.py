import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from httpx import AsyncClient, HTTPStatusError, Response, Request
from port_ocean.context.event import event_context
from typing import Any, AsyncGenerator, Generator, Dict, List
from client import BitbucketClient
from helpers.multiple_token_handler import MultiTokenBitbucketClient


@pytest.fixture
def mock_http_client() -> AsyncClient:
    """Create a mock HTTP client."""
    client = AsyncMock(spec=AsyncClient)
    # Ensure headers is a dict-like object that can be accessed with __getitem__
    client.headers = {}
    return client


@pytest.fixture
def mock_integration_config() -> Generator[Dict[str, str], None, None]:
    """Mock the ocean integration config."""
    config = {
        "bitbucket_workspace": "test_workspace",
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
    mock_integration_config: Dict[str, str]
) -> AsyncGenerator[BitbucketClient, None]:
    """Create BitbucketClient using create_from_ocean_config."""
    # Use a real http_client mock with proper headers
    http_client = AsyncMock(spec=AsyncClient)
    http_client.headers = {}

    with patch("helpers.multiple_token_handler.http_async_client", http_client):
        client = BitbucketClient.create_from_ocean_config()
        yield client


@pytest.mark.asyncio
async def test_client_init_with_token() -> None:
    """Test client initialization with token auth."""
    config = {
        "bitbucket_workspace": "test_workspace",
        "bitbucket_workspace_token": "test_token",
    }

    # Use a real http_client mock with proper headers dictionary
    http_client = AsyncMock(spec=AsyncClient)
    http_client.headers = {}

    with (
        patch(
            "port_ocean.context.ocean.PortOceanContext.integration_config",
            new_callable=PropertyMock,
        ) as mock_config,
        patch("helpers.multiple_token_handler.http_async_client", http_client),
    ):
        mock_config.return_value = config
        BitbucketClient.create_from_ocean_config()

        # Verify the Authorization header was set correctly
        assert http_client.headers["Authorization"] == "Bearer test_token"


@pytest.mark.asyncio
async def test_client_init_with_app_password(
    mock_integration_config: Dict[str, str]
) -> None:
    """Test client initialization with app password auth."""
    # Use a real http_client mock with proper headers dictionary
    http_client = AsyncMock(spec=AsyncClient)
    http_client.headers = {}

    with patch("helpers.multiple_token_handler.http_async_client", http_client):
        BitbucketClient.create_from_ocean_config()

        # Verify the Authorization header was set correctly
        assert "Basic" in http_client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_no_auth() -> None:
    """Test client initialization with no auth raises error."""
    config = {"bitbucket_workspace": "test_workspace"}
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        with pytest.raises(ValueError) as exc_info:
            BitbucketClient.create_from_ocean_config()
        assert "No valid credentials found in config" in str(exc_info.value)


@pytest.mark.asyncio
async def test_send_api_request_success(mock_client: BitbucketClient) -> None:
    """Test successful API request."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}

    # Mock the rate_limit context manager
    with (
        patch.object(
            mock_client.get_current_client().client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(MultiTokenBitbucketClient, "rate_limit") as mock_rate_limit,
    ):
        # Set up the mock context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = False  # No rotation needed
        mock_rate_limit.return_value = mock_context

        # Set up request mock
        mock_request.return_value = mock_response

        # Test the request
        result = await mock_client._send_api_request("test/endpoint")

        # Verify results
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.bitbucket.org/2.0/test/endpoint",
            params=None,
            json=None,
        )
        mock_rate_limit.assert_called_once_with("test/endpoint")


@pytest.mark.asyncio
async def test_send_api_request_with_client_rotation(
    mock_client: BitbucketClient,
) -> None:
    """Test API request with client rotation."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}

    # Add a second client to the mock client
    mock_client.token_clients.append(mock_client.token_clients[0])

    # Modify the _send_api_request method with a patched version for this test
    with patch.object(
        mock_client, "_send_api_request", wraps=mock_client._send_api_request
    ) as wrapped_send:
        # Mock the rate_limit context manager and client.request directly
        with (
            patch.object(
                mock_client.get_current_client().client,
                "request",
                new_callable=AsyncMock,
            ) as mock_request,
            patch.object(mock_client, "_rotate_client") as mock_rotate,
            patch("client.logger.warning") as mock_logger,
        ):
            # Setup request to fail first with 429, then succeed
            mock_error_response = MagicMock(spec=Response)
            mock_error_response.status_code = 429
            mock_error_response.raise_for_status.side_effect = HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(spec=Request),
                response=mock_error_response,
            )

            # First call - 429 error response
            # Second call - success response
            mock_request.side_effect = [mock_error_response, mock_response]

            # Test the request - need to call original to trigger error handling
            await wrapped_send("repositories/test-repo")

            # Verify results
            assert mock_request.call_count >= 1
            mock_rotate.assert_called_once()  # Client rotation should have been called
            mock_logger.assert_called_with("Rate limit hit, rotating client")


@pytest.mark.asyncio
async def test_send_api_request_with_rate_limit_error(
    mock_client: BitbucketClient,
) -> None:
    """Test API request with rate limit error (HTTP 429)."""
    # Create a mock 429 response
    mock_error_response = MagicMock(spec=Response)
    mock_error_response.status_code = 429
    mock_error_response.json.return_value = {
        "error": {"message": "Rate limit exceeded"}
    }

    # Create a successful response for the retry
    mock_success_response = MagicMock(spec=Response)
    mock_success_response.raise_for_status = MagicMock()
    mock_success_response.json.return_value = {"data": "success after retry"}

    # Setup HTTP error
    http_error = HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(spec=Request),
        response=mock_error_response,
    )

    with (
        patch.object(
            mock_client.get_current_client().client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(MultiTokenBitbucketClient, "rate_limit") as mock_rate_limit,
        patch.object(mock_client, "_rotate_client") as mock_rotate,
        patch("client.logger.warning") as mock_logger_warning,
    ):
        # Set up the mock context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = False  # No rotation by context
        mock_rate_limit.return_value = mock_context

        # Set up request to fail with 429 on first call, then succeed
        # Set up the first response to raise an error when raise_for_status is called
        mock_error_response.raise_for_status.side_effect = http_error

        # Add a second client to trigger rotation
        mock_client.token_clients.append(mock_client.token_clients[0])

        with patch.object(
            mock_client, "_send_api_request", wraps=mock_client._send_api_request
        ) as wrapped_send:
            mock_request.side_effect = [mock_error_response, mock_success_response]

            result = await wrapped_send("test/endpoint")
        # Verify results
        assert result == {"data": "success after retry"}
        assert mock_request.call_count == 2
        mock_rotate.assert_called_once()
        mock_logger_warning.assert_called_with("Rate limit hit, rotating client")


@pytest.mark.asyncio
async def test_send_api_request_raises_exception_on_non_rate_limit_error(
    mock_client: BitbucketClient,
) -> None:
    """Test API request with general exception followed by success."""
    mock_success_response = MagicMock(spec=Response)
    mock_success_response.raise_for_status = MagicMock()

    with (
        patch.object(
            mock_client.get_current_client().client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(MultiTokenBitbucketClient, "rate_limit") as mock_rate_limit,
        patch.object(mock_client, "_rotate_client") as mock_rotate,
        patch("client.logger.error") as mock_logger_error,
    ):
        # Set up the mock context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = False  # No rotation by context
        mock_rate_limit.return_value = mock_context
        mock_request.side_effect = Exception("Network error")

        # The test should expect the exception to be raised
        with pytest.raises(Exception, match="Network error"):
            await mock_client._send_api_request("test/endpoint")

        # Verify result
        mock_rotate.assert_not_called()
        mock_logger_error.assert_called_with("Request failed: Network error")


@pytest.mark.asyncio
async def test_send_api_request_with_params(mock_client: BitbucketClient) -> None:
    """Test API request with query parameters."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    params = {"page": 1, "pagelen": 100}

    with (
        patch.object(
            mock_client.get_current_client().client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(MultiTokenBitbucketClient, "rate_limit") as mock_rate_limit,
    ):
        # Set up the mock context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = False  # No rotation needed
        mock_rate_limit.return_value = mock_context

        # Set up request mock
        mock_request.return_value = mock_response

        # Test the request
        result = await mock_client._send_api_request("test/endpoint", params=params)

        # Verify results
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.bitbucket.org/2.0/test/endpoint",
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

    with (
        patch.object(
            mock_client.get_current_client().client, "request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(MultiTokenBitbucketClient, "rate_limit") as mock_rate_limit,
        patch("client.logger.error") as mock_logger,
    ):
        # Set up the mock context manager
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = False  # No rotation needed
        mock_rate_limit.return_value = mock_context

        # Make the request raise an error
        mock_request.return_value = mock_response
        mock_response.raise_for_status.side_effect = original_error

        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_client._send_api_request("test/endpoint")

        assert exc_info.value == original_error
        mock_logger.assert_called_once_with("Bitbucket API error: Test error message")


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
        async for batch in mock_client._send_paginated_api_request("test/endpoint"):
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

            async def mock_generator() -> AsyncGenerator[List[Dict[str, Any]], None]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for projects in mock_client.get_projects():
                assert projects == mock_data["values"]
            mock_paginated.assert_called_once_with("workspaces/test_workspace/projects")


@pytest.mark.asyncio
async def test_get_repositories(mock_client: BitbucketClient) -> None:
    """Test getting repositories."""
    mock_data = {"values": [{"slug": "test-repo", "name": "Test Repo"}]}
    async with event_context("test_event"):
        with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

            async def mock_generator() -> AsyncGenerator[List[Dict[str, Any]], None]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for repos in mock_client.get_repositories():
                assert repos == mock_data["values"]
            mock_paginated.assert_called_once_with("repositories/test_workspace")


@pytest.mark.asyncio
async def test_get_directory_contents(mock_client: BitbucketClient) -> None:
    """Test getting directory contents."""
    mock_dir_data = {"values": [{"type": "commit_directory", "path": "src"}]}

    with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

        async def mock_generator() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_dir_data["values"]

        mock_paginated.return_value = mock_generator()

        # First test - use the exact param format that the actual implementation uses
        async for contents in mock_client.get_directory_contents(
            "test-repo", "main", ""
        ):
            assert contents == mock_dir_data["values"]

        # Check that it's called with exactly the params from the implementation
        # Including pagelen as it's set in _send_paginated_api_request
        expected_params = {"max_depth": 2, "pagelen": 100}
        mock_paginated.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/src/main/",
            params=expected_params,
        )

        # Reset mock for second test
        mock_paginated.reset_mock()
        mock_paginated.return_value = mock_generator()

        # Second test with explicit max_depth
        async for contents in mock_client.get_directory_contents(
            "test-repo", "main", "", max_depth=4
        ):
            assert contents == mock_dir_data["values"]

        # Check with updated expected params, including pagelen
        mock_paginated.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/src/main/",
            params={"max_depth": 4, "pagelen": 100},
        )


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client: BitbucketClient) -> None:
    """Test getting pull requests."""
    mock_data = {"values": [{"id": 1, "title": "Test PR"}]}

    with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

        async def mock_generator() -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_data["values"]

        mock_paginated.return_value = mock_generator()

        async for prs in mock_client.get_pull_requests("test-repo"):
            assert prs == mock_data["values"]

        # Include state param in expected call since that's what the implementation uses
        mock_paginated.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/pullrequests",
            params={"state": "OPEN"},
        )
