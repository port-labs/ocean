import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, HTTPStatusError
from port_ocean.context.event import event_context
from typing import Any, AsyncIterator
from bitbucket_cloud.client import BitbucketClient
from bitbucket_cloud.helpers.exceptions import MissingIntegrationCredentialException
from bitbucket_cloud.base_client import BitbucketBaseClient


@pytest.fixture
def mock_http_client() -> AsyncClient:
    """Create a mock HTTP client."""
    return AsyncMock(spec=AsyncClient)


@pytest.fixture
def mock_integration_config() -> MagicMock:
    """Create a mock integration configuration."""
    config = MagicMock()
    config.get.return_value = {
        "workspace": "test-workspace",
        "host": "https://api.bitbucket.org/2.0",
    }
    return config


@pytest.fixture
def mock_client(mock_integration_config: MagicMock) -> BitbucketClient:
    """Create a BitbucketClient with mocked configuration."""
    with patch("port_ocean.utils.http_async_client", new_callable=AsyncMock):
        base_client = BitbucketBaseClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            username="test-user",
            app_password="test-password",
        )
        client = BitbucketClient()
        client.set_base_client(base_client)
        return client


@pytest.mark.asyncio
async def test_client_init_with_token(mock_integration_config: MagicMock) -> None:
    """Test client initialization with token authentication."""
    with patch("port_ocean.utils.http_async_client", new_callable=AsyncMock):
        base_client = BitbucketBaseClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            workspace_token="test-token",
        )
        client = BitbucketClient()
        client.set_base_client(base_client)
        assert client.workspace == "test-workspace"
        assert client.base_url == "https://api.bitbucket.org/2.0"
        assert "Bearer" in client.base_client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_with_app_password(
    mock_integration_config: MagicMock,
) -> None:
    """Test client initialization with app password authentication."""
    with patch("port_ocean.utils.http_async_client", new_callable=AsyncMock):
        base_client = BitbucketBaseClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
            username="test-user",
            app_password="test-password",
        )
        client = BitbucketClient()
        client.set_base_client(base_client)
        assert client.workspace == "test-workspace"
        assert client.base_url == "https://api.bitbucket.org/2.0"
        assert "Basic" in client.base_client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_no_auth(mock_integration_config: MagicMock) -> None:
    """Test client initialization without authentication."""
    with pytest.raises(MissingIntegrationCredentialException) as exc_info:
        BitbucketBaseClient(
            workspace="test-workspace",
            host="https://api.bitbucket.org/2.0",
        )
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
        mock_client.base_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"data": "test"}
        async for batch in mock_client._send_paginated_api_request(
            f"{mock_client.base_url}/test/endpoint"
        ):
            assert batch == []
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params={"pagelen": 100},
        )


@pytest.mark.asyncio
async def test_send_api_request_with_params(mock_client: BitbucketClient) -> None:
    """Test API request with query parameters."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": "test"}
    params = {"page": 1, "pagelen": 100}
    with patch.object(
        mock_client.base_client, "send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"data": "test"}
        async for batch in mock_client._send_paginated_api_request(
            f"{mock_client.base_url}/test/endpoint", params=params
        ):
            assert batch == []
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params=params,
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
            mock_client.base_client, "send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch("bitbucket_cloud.client.logger.error") as mock_logger,
    ):
        mock_request.side_effect = original_error

        with pytest.raises(HTTPStatusError) as exc_info:
            async for _ in mock_client._send_paginated_api_request(
                f"{mock_client.base_url}/test/endpoint"
            ):
                pass

        assert exc_info.value == original_error
        mock_logger.assert_called()
        mock_request.assert_called_once_with(
            method="GET",
            url=f"{mock_client.base_url}/test/endpoint",
            params={"pagelen": 100},
        )


@pytest.mark.asyncio
async def test_send_paginated_api_request(mock_client: BitbucketClient) -> None:
    """Test paginated API request."""
    page1 = {
        "values": [{"id": 1}, {"id": 2}],
        "next": "https://api.bitbucket.org/2.0/test/endpoint?page=2",
    }
    page2 = {"values": [{"id": 3}], "next": None}
    with patch.object(
        mock_client.base_client, "send_api_request", new_callable=AsyncMock
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
                f"{mock_client.base_url}/workspaces/{mock_client.workspace}/projects"
            )


@pytest.mark.asyncio
async def test_get_repositories(mock_client: BitbucketClient) -> None:
    """Test getting repositories."""
    mock_data = {"values": [{"slug": "test-repo", "name": "Test Repo"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_send_rate_limited_paginated_api_request"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for repos in mock_client.get_repositories():
                assert repos == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/{mock_client.workspace}",
                params=None,
            )


@pytest.mark.asyncio
async def test_get_directory_contents(mock_client: BitbucketClient) -> None:
    """Test getting directory contents."""
    mock_dir_data = {"values": [{"type": "commit_directory", "path": "src"}]}

    async with event_context("test_event"):
        with patch.object(
            mock_client, "_send_rate_limited_paginated_api_request"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_dir_data["values"]

            mock_paginated.return_value = mock_generator()
            async for contents in mock_client.get_directory_contents(
                "test-repo", "main", ""
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
            mock_client, "_send_rate_limited_paginated_api_request"
        ) as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_data["values"]

            mock_paginated.return_value = mock_generator()
            async for prs in mock_client._get_pull_requests("test-repo"):
                assert prs == mock_data["values"]
            mock_paginated.assert_called_once_with(
                f"{mock_client.base_url}/repositories/{mock_client.workspace}/test-repo/pullrequests",
                params={"state": "OPEN", "pagelen": 50},
            )


@pytest.mark.asyncio
async def test_get_all_pull_requests(mock_client: BitbucketClient) -> None:
    """Test getting all pull requests from all repositories."""
    mock_repos = [{"slug": "test-repo", "name": "Test Repo"}]
    mock_prs = [{"id": 1, "title": "Test PR"}]

    async with event_context("test_event"):
        with (
            patch.object(mock_client, "get_repositories") as mock_get_repos,
            patch.object(mock_client, "_get_pull_requests") as mock_get_prs,
        ):

            async def mock_repos_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_repos

            async def mock_prs_generator() -> AsyncIterator[list[dict[str, Any]]]:
                yield mock_prs

            mock_get_repos.return_value = mock_repos_generator()
            mock_get_prs.return_value = mock_prs_generator()

            async for prs in mock_client.get_pull_requests():
                assert prs == mock_prs

            mock_get_repos.assert_called_once()
            mock_get_prs.assert_called_once_with("test-repo")
