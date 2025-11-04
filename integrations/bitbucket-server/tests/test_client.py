from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, Response

from client import (
    BitbucketClient,
    DEFAULT_BITBUCKET_RATE_LIMIT,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_PAGE_SIZE,
)


@pytest.fixture
def mock_client() -> BitbucketClient:
    """Create a mocked Bitbucket Server client."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        webhook_secret="test-secret",
        app_host="https://app.example.com",
    )
    client.client = MagicMock(spec=AsyncClient)
    return client


@pytest.mark.asyncio
async def test_send_port_request(mock_client: BitbucketClient) -> None:
    """Test sending a request to the Bitbucket API."""
    # Arrange
    expected_response = {"key": "TEST", "name": "Test Project"}
    mock_response = MagicMock(spec=Response)
    mock_response.json = MagicMock(return_value=expected_response)
    mock_response.raise_for_status = MagicMock()
    mock_client.client.request.return_value = mock_response  # type: ignore[attr-defined]

    # Act
    response = await mock_client._send_api_request("GET", "projects/TEST")

    # Assert
    assert response == expected_response
    mock_client.client.request.assert_called_once()  # type: ignore[attr-defined]
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_paginated_resource(mock_client: BitbucketClient) -> None:
    """Test getting paginated resources from the Bitbucket API."""
    # Arrange
    mock_responses = [
        {
            "values": [{"id": 1}, {"id": 2}],
            "isLastPage": False,
            "nextPageStart": 2,
        },
        {
            "values": [{"id": 3}],
            "isLastPage": True,
        },
    ]
    mock_client._send_api_request = AsyncMock(side_effect=mock_responses)  # type: ignore[method-assign]

    # Act
    results = []
    async for batch in mock_client.get_paginated_resource("projects"):
        results.extend(batch)

    # Assert
    assert len(results) == 3
    assert [r["id"] for r in results] == [1, 2, 3]
    assert mock_client._send_api_request.call_count == 2


@pytest.mark.asyncio
async def test_healthcheck(mock_client: BitbucketClient) -> None:
    """Test health check functionality."""
    # Arrange
    mock_client._get_application_properties = AsyncMock(  # type: ignore[method-assign]
        return_value={"version": "8.8.0"}
    )

    # Act & Assert
    await mock_client.healthcheck()  # Should not raise an exception


@pytest.mark.asyncio
async def test_healthcheck_failure(mock_client: BitbucketClient) -> None:
    """Test health check failure."""
    # Arrange
    mock_client._get_application_properties = AsyncMock(  # type: ignore[method-assign]
        side_effect=Exception("Connection failed")
    )
    # Act & Assert
    with pytest.raises(ConnectionError):
        await mock_client.healthcheck()


@pytest.mark.asyncio
async def test_configurable_page_size() -> None:
    """Test that page size is configurable and used in pagination."""
    custom_page_size = 100
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        page_size=custom_page_size,
    )
    client.client = MagicMock(spec=AsyncClient)

    mock_response = MagicMock(spec=Response)
    mock_response.json = MagicMock(
        return_value={"values": [{"id": 1}], "isLastPage": True}
    )
    mock_response.raise_for_status = MagicMock()
    client.client.request = AsyncMock(return_value=mock_response)

    results = []
    async for batch in client.get_paginated_resource("test"):
        results.extend(batch)

    assert client.page_size == custom_page_size
    call_args = client.client.request.call_args
    assert call_args is not None
    assert call_args[1]["params"]["limit"] == custom_page_size


@pytest.mark.asyncio
async def test_default_page_size() -> None:
    """Test that default page size is used when not specified."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
    )

    assert client.page_size == DEFAULT_PAGE_SIZE


@pytest.mark.asyncio
async def test_configurable_rate_limit() -> None:
    """Test that rate limit is configurable."""
    custom_rate_limit = 2000
    custom_window = 7200

    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        rate_limit=custom_rate_limit,
        rate_limit_window=custom_window,
    )

    assert client.rate_limiter.max_rate == custom_rate_limit
    assert client.rate_limiter.time_period == custom_window


@pytest.mark.asyncio
async def test_default_rate_limit() -> None:
    """Test that default rate limit is used when not specified."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
    )

    assert client.rate_limiter.max_rate == DEFAULT_BITBUCKET_RATE_LIMIT
    assert client.rate_limiter.time_period == 3600


@pytest.mark.asyncio
async def test_configurable_concurrency() -> None:
    """Test that max concurrent requests is configurable."""
    custom_concurrency = 50

    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        max_concurrent_requests=custom_concurrency,
    )

    assert client.max_concurrent_requests == custom_concurrency
    assert client.pr_semaphore._value == custom_concurrency


@pytest.mark.asyncio
async def test_default_concurrency() -> None:
    """Test that default concurrency is used when not specified."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
    )

    assert client.max_concurrent_requests == DEFAULT_MAX_CONCURRENT_REQUESTS
    assert client.pr_semaphore._value == DEFAULT_MAX_CONCURRENT_REQUESTS


@pytest.mark.asyncio
async def test_project_filtering_with_prefix_regex() -> None:
    """Test project filtering with prefix regex pattern."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        project_filter_regex="^PROD-.*",
    )

    assert client._should_include_project("PROD-123") is True
    assert client._should_include_project("PROD-ABC") is True
    assert client._should_include_project("DEV-123") is False
    assert client._should_include_project("TEST-ABC") is False


@pytest.mark.asyncio
async def test_project_filtering_with_suffix_regex() -> None:
    """Test project filtering with suffix regex pattern."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        project_filter_regex=".*-PROD$",
    )

    assert client._should_include_project("PROJECT-PROD") is True
    assert client._should_include_project("TEAM-PROD") is True
    assert client._should_include_project("PROJECT-DEV") is False
    assert client._should_include_project("TEAM-TEST") is False


@pytest.mark.asyncio
async def test_project_filtering_with_combined_regex() -> None:
    """Test project filtering with combined prefix and suffix regex."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        project_filter_regex="^TEAM-.*-PROD$",
    )

    assert client._should_include_project("TEAM-APP-PROD") is True
    assert client._should_include_project("TEAM-API-PROD") is True
    assert client._should_include_project("TEAM-APP-DEV") is False
    assert client._should_include_project("PROJECT-APP-PROD") is False
    assert client._should_include_project("PROJECT-APP-DEV") is False


@pytest.mark.asyncio
async def test_project_filtering_disabled_by_default() -> None:
    """Test that project filtering is disabled when no patterns are provided."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
    )

    assert client._should_include_project("ANY-PROJECT") is True
    assert client._should_include_project("ANOTHER-ONE") is True
    assert client._should_include_project("TEST") is True


@pytest.mark.asyncio
async def test_project_filtering_logic_with_regex() -> None:
    """Test that project filtering logic works correctly with regex."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        project_filter_regex="^PROD-.*",
    )

    test_projects = [
        {"key": "PROD-123", "name": "Production 123"},
        {"key": "DEV-456", "name": "Development 456"},
        {"key": "PROD-789", "name": "Production 789"},
        {"key": "TEST-001", "name": "Test 001"},
    ]

    filtered = [p for p in test_projects if client._should_include_project(p["key"])]

    assert len(filtered) == 2
    assert all(p["key"].startswith("PROD-") for p in filtered)
    assert filtered[0]["key"] == "PROD-123"
    assert filtered[1]["key"] == "PROD-789"


@pytest.mark.asyncio
async def test_parallel_pr_fetching_uses_semaphore() -> None:
    """Test that PR fetching uses semaphore for concurrency control."""
    max_concurrent = 5
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
        max_concurrent_requests=max_concurrent,
    )

    assert client.pr_semaphore._value == max_concurrent
    assert client.max_concurrent_requests == max_concurrent
