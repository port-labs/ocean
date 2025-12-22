"""Unit tests for HarborClient."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import BasicAuth, Request, Response

from harbor.client import HarborClient, PAGE_SIZE


@pytest.mark.asyncio
async def test_client_initialization(mock_harbor_client: HarborClient) -> None:
    """Test the correct initialization of HarborClient with authentication."""
    assert mock_harbor_client.base_url == "https://harbor.example.com"
    assert isinstance(mock_harbor_client.client.auth, BasicAuth)


@pytest.mark.asyncio
async def test_client_initialization_no_auth(
    mock_harbor_client_no_auth: HarborClient,
) -> None:
    """Test the correct initialization of HarborClient without authentication."""
    assert mock_harbor_client_no_auth.base_url == "https://harbor.example.com"
    assert mock_harbor_client_no_auth.client.auth is None


@pytest.mark.asyncio
async def test_send_api_request_success(mock_harbor_client: HarborClient) -> None:
    """Test successful API requests."""
    with patch.object(
        mock_harbor_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            200,
            request=Request("GET", "http://example.com"),
            json={"key": "value"},
        )
        response = await mock_harbor_client._send_api_request(
            "GET", "/api/v2.0/projects"
        )
        assert response["key"] == "value"


@pytest.mark.asyncio
async def test_send_api_request_failure(mock_harbor_client: HarborClient) -> None:
    """Test API request raising exceptions for non-429 errors."""
    with patch.object(
        mock_harbor_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            404, request=Request("GET", "http://example.com")
        )
        with pytest.raises(Exception):
            await mock_harbor_client._send_api_request("GET", "/api/v2.0/projects")


@pytest.mark.asyncio
async def test_send_api_request_rate_limit_retry(
    mock_harbor_client: HarborClient,
) -> None:
    """Test API request retries on 429 rate limit."""
    with patch.object(
        mock_harbor_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        # First call returns 429, second call succeeds
        mock_request.side_effect = [
            Response(
                429,
                request=Request("GET", "http://example.com"),
                headers={"Retry-After": "1"},
            ),
            Response(
                200,
                request=Request("GET", "http://example.com"),
                json={"key": "value"},
            ),
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await mock_harbor_client._send_api_request(
                "GET", "/api/v2.0/projects"
            )
            assert response["key"] == "value"
            assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_extract_items_from_response_list() -> None:
    """Test extracting items from a list response."""
    response = [{"id": 1}, {"id": 2}]
    items = HarborClient._extract_items_from_response(response)
    assert items == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_extract_items_from_response_dict_with_items() -> None:
    """Test extracting items from a dict response with 'items' key."""
    response = {"items": [{"id": 1}, {"id": 2}], "total": 2}
    items = HarborClient._extract_items_from_response(response)
    assert items == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_extract_items_from_response_dict_with_data() -> None:
    """Test extracting items from a dict response with 'data' key."""
    response = {"data": [{"id": 1}, {"id": 2}]}
    items = HarborClient._extract_items_from_response(response)
    assert items == [{"id": 1}, {"id": 2}]


@pytest.mark.asyncio
async def test_extract_items_from_response_empty() -> None:
    """Test extracting items from an empty or invalid response."""
    response = {}
    items = HarborClient._extract_items_from_response(response)
    assert items == []


@pytest.mark.asyncio
async def test_get_paginated_resources(mock_harbor_client: HarborClient) -> None:
    """Test paginated resource fetching."""
    with patch.object(
        mock_harbor_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        # First page with full results, second page with fewer results
        mock_request.side_effect = [
            [{"id": 1}, {"id": 2}],
            [{"id": 3}],  # Less than page_size, should stop pagination
        ]

        results = []
        async for batch in mock_harbor_client.get_paginated_resources(
            "/api/v2.0/projects",
        ):
            results.extend(batch)

        assert len(results) == 3
        assert results[0]["id"] == 1
        assert results[2]["id"] == 3
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_get_paginated_resources_empty_response(
    mock_harbor_client: HarborClient,
) -> None:
    """Test paginated resource fetching with empty first page."""
    with patch.object(
        mock_harbor_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = []

        results = []
        async for batch in mock_harbor_client.get_paginated_resources(
            "/api/v2.0/projects"
        ):
            results.extend(batch)

        assert len(results) == 0
        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_get_projects(mock_harbor_client: HarborClient) -> None:
    """Test get_projects method."""
    projects_data: list[dict[str, Any]] = [
        {"project_id": 1, "name": "Project 1"},
        {"project_id": 2, "name": "Project 2"},
    ]

    # Create async generator function
    async def mock_generator(*args: Any, **kwargs: Any) -> Any:
        yield projects_data

    # Patch the method to return the generator
    with patch.object(
        mock_harbor_client, "get_paginated_resources"
    ) as mock_paginated:
        mock_paginated.return_value = mock_generator()

        projects: list[dict[str, Any]] = []
        async for project_batch in mock_harbor_client.get_projects(
            params={"public": "true"}
        ):
            projects.extend(project_batch)

        assert len(projects) == 2
        assert projects[0]["name"] == "Project 1"


@pytest.mark.asyncio
async def test_get_repositories(mock_harbor_client: HarborClient) -> None:
    """Test get_repositories method."""
    repos_data: list[dict[str, Any]] = [
        {"id": 1, "name": "library/nginx"},
        {"id": 2, "name": "library/redis"},
    ]

    async def mock_generator(*args: Any, **kwargs: Any) -> Any:
        yield repos_data

    with patch.object(
        mock_harbor_client, "get_paginated_resources"
    ) as mock_paginated:
        mock_paginated.return_value = mock_generator()

        repos: list[dict[str, Any]] = []
        async for repo_batch in mock_harbor_client.get_repositories():
            repos.extend(repo_batch)

        assert len(repos) == 2
        assert repos[0]["name"] == "library/nginx"


@pytest.mark.asyncio
async def test_get_artifacts_for_repository(mock_harbor_client: HarborClient) -> None:
    """Test get_artifacts_for_repository method."""
    artifacts_data: list[dict[str, Any]] = [
        {"digest": "sha256:abc123", "tags": [{"name": "latest"}]},
        {"digest": "sha256:def456", "tags": [{"name": "v1.0"}]},
    ]

    async def mock_generator(*args: Any, **kwargs: Any) -> Any:
        yield artifacts_data

    with patch.object(
        mock_harbor_client, "get_paginated_resources"
    ) as mock_paginated:
        mock_paginated.return_value = mock_generator()

        artifacts: list[dict[str, Any]] = []
        async for artifact_batch in mock_harbor_client.get_artifacts_for_repository(
            project_name="library", repository_name="nginx"
        ):
            artifacts.extend(artifact_batch)

        assert len(artifacts) == 2
        assert artifacts[0]["digest"] == "sha256:abc123"


@pytest.mark.asyncio
async def test_get_single_artifact_success(mock_harbor_client: HarborClient) -> None:
    """Test get_single_artifact method with successful fetch."""
    artifact_data: dict[str, Any] = {
        "digest": "sha256:abc123",
        "tags": [{"name": "latest"}],
        "size": 12345,
    }

    with patch.object(
        mock_harbor_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = artifact_data

        result = await mock_harbor_client.get_single_artifact(
            project_name="library",
            repository_name="nginx",
            reference="latest",
        )

        assert result == artifact_data
        mock_request.assert_called_once()


@pytest.mark.asyncio
async def test_get_single_artifact_not_found(mock_harbor_client: HarborClient) -> None:
    """Test get_single_artifact method when artifact is not found."""
    with patch.object(
        mock_harbor_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        from httpx import HTTPStatusError

        response = Response(
            404,
            request=Request(
                "GET",
                "https://harbor.example.com/api/v2.0/projects/library/repositories/nginx/artifacts/latest",
            ),
        )
        mock_request.side_effect = HTTPStatusError(
            "Not Found", request=response.request, response=response
        )

        result = await mock_harbor_client.get_single_artifact(
            project_name="library",
            repository_name="nginx",
            reference="latest",
        )

        assert result is None


@pytest.mark.asyncio
async def test_get_users(mock_harbor_client: HarborClient) -> None:
    """Test get_users method."""
    users_data: list[dict[str, Any]] = [
        {"user_id": 1, "username": "admin"},
        {"user_id": 2, "username": "developer"},
    ]

    async def mock_generator(*args: Any, **kwargs: Any) -> Any:
        yield users_data

    with patch.object(
        mock_harbor_client, "get_paginated_resources"
    ) as mock_paginated:
        mock_paginated.return_value = mock_generator()

        users: list[dict[str, Any]] = []
        async for user_batch in mock_harbor_client.get_users():
            users.extend(user_batch)

        assert len(users) == 2
        assert users[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_get_paginated_resources_with_params(
    mock_harbor_client: HarborClient,
) -> None:
    """Test paginated resources with custom parameters."""
    with patch.object(
        mock_harbor_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            [{"id": 1}],
            [],  # Empty response to stop pagination
        ]

        results = []
        async for batch in mock_harbor_client.get_paginated_resources(
            "/api/v2.0/projects",
            params={"public": "true"},
        ):
            results.extend(batch)

        # Verify params were passed correctly
        call_args = mock_request.call_args_list[0]
        assert call_args[1]["params"]["public"] == "true"
        assert call_args[1]["params"]["page"] == 1
        assert call_args[1]["params"]["page_size"] == 10

