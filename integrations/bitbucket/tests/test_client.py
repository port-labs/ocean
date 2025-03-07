import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, HTTPStatusError, Response
from port_ocean.context.event import event_context
from typing import Any, AsyncIterator, Iterator
from bitbucket_integration.client import BitbucketClient


class AsyncIteratorMock:
    """Helper class to mock async iterators."""

    def __init__(self, items: Iterator[Any]) -> None:
        self.items = items

    def __aiter__(self) -> "AsyncIteratorMock":
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def mock_client(mock_http_client: AsyncClient) -> BitbucketClient:
    """Create BitbucketClient with mocked HTTP client."""
    return BitbucketClient(
        workspace="test_workspace", username="test_user", app_password="test_password"
    )


@pytest.mark.asyncio
async def test_client_init_with_token() -> None:
    """Test client initialization with token auth."""
    client = BitbucketClient(workspace="test_workspace", workspace_token="test_token")
    assert "Bearer test_token" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_with_app_password() -> None:
    """Test client initialization with app password auth."""
    client = BitbucketClient(
        workspace="test_workspace", username="test_user", app_password="test_password"
    )
    assert "Basic" in client.headers["Authorization"]


@pytest.mark.asyncio
async def test_client_init_no_auth() -> None:
    """Test client initialization with no auth raises error."""
    with pytest.raises(ValueError) as exc_info:
        BitbucketClient(workspace="test_workspace")
    assert (
        "Either workspace_token or both username and app_password must be provided"
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
        result = await mock_client._send_api_request("test/endpoint")
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.bitbucket.org/2.0/test/endpoint",
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
        result = await mock_client._send_api_request("test/endpoint", params=params)
        assert result == {"data": "test"}
        mock_request.assert_called_once_with(
            method="GET",
            url="https://api.bitbucket.org/2.0/test/endpoint",
            params=params,
            json=None,
        )


@pytest.mark.asyncio
async def test_send_api_request_error(mock_client: BitbucketClient) -> None:
    """Test API request with error response."""
    error_response = Response(400, json={"error": {"message": "Test error"}})
    mock_error = HTTPStatusError(
        "Test error", request=MagicMock(), response=error_response
    )
    with patch.object(
        mock_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = mock_error
        with pytest.raises(HTTPStatusError) as exc_info:
            await mock_client._send_api_request("test/endpoint")
        assert "Test error" in str(exc_info.value)


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
        results = []
        async for batch in mock_client._send_paginated_api_request("test/endpoint"):
            results.extend(batch)
        assert len(results) == 3
        assert [item["id"] for item in results] == [1, 2, 3]
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
            mock_paginated.assert_called_once_with("workspaces/test_workspace/projects")


@pytest.mark.asyncio
async def test_get_repositories(mock_client: BitbucketClient) -> None:
    """Test getting repositories."""
    mock_data = {"values": [{"slug": "test-repo", "name": "Test Repo"}]}
    async with event_context("test_event"):
        with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

            async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
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

        async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
            yield mock_dir_data["values"]

        mock_paginated.return_value = mock_generator()
        async for contents in mock_client.get_directory_contents(
            "test-repo", "main", ""
        ):
            assert contents == mock_dir_data["values"]
        mock_paginated.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/src/main/",
            params={"max_depth": 2, "pagelen": 100},
        )
        mock_paginated.reset_mock()
        async for contents in mock_client.get_directory_contents(
            "test-repo", "main", "", max_depth=4
        ):
            assert contents == mock_dir_data["values"]
        mock_paginated.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/src/main/",
            params={"max_depth": 4, "pagelen": 100},
        )


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client: BitbucketClient) -> None:
    """Test getting pull requests."""
    mock_data = {"values": [{"id": 1, "title": "Test PR"}]}

    with patch.object(mock_client, "_send_paginated_api_request") as mock_paginated:

        async def mock_generator() -> AsyncIterator[list[dict[str, Any]]]:
            yield mock_data["values"]

        mock_paginated.return_value = mock_generator()

        async for prs in mock_client.get_pull_requests("test-repo"):
            assert prs == mock_data["values"]

        mock_paginated.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/pullrequests"
        )


@pytest.mark.asyncio
async def test_get_pull_request(mock_client: BitbucketClient) -> None:
    """Test getting a pull request."""
    mock_data = {"values": {"id": 1, "title": "Test PR"}}
    with patch.object(mock_client, "_send_api_request") as mock_request:
        mock_request.return_value = mock_data
        pr = await mock_client.get_pull_request("test-repo", 1)
        assert pr["values"] == mock_data["values"]
        mock_request.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo/pullrequests/1"
        )


@pytest.mark.asyncio
async def test_get_repository(mock_client: BitbucketClient) -> None:
    """Test getting a repository."""
    mock_data = {"values": {"id": 1, "title": "Test Repo"}}
    with patch.object(mock_client, "_send_api_request") as mock_request:
        mock_request.return_value = mock_data
        repo = await mock_client.get_repository("test-repo")
        assert repo["values"] == mock_data["values"]
        mock_request.assert_called_once_with(
            f"repositories/{mock_client.workspace}/test-repo"
        )
