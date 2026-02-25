import re
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, Response

from client import (
    BitbucketClient,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    DEFAULT_PAGE_SIZE,
)

SPEC_DEFAULT_RATE_LIMIT = 1000
SPEC_DEFAULT_RATE_LIMIT_WINDOW = 3600


def _build_client(**overrides: Any) -> BitbucketClient:
    base_kwargs: dict[str, Any] = {
        "base_url": "https://bitbucket.example.com",
        "username": "test-user",
        "password": "test-password",
        "rate_limit": SPEC_DEFAULT_RATE_LIMIT,
        "rate_limit_window": SPEC_DEFAULT_RATE_LIMIT_WINDOW,
    }
    base_kwargs.update(overrides)
    return BitbucketClient(**base_kwargs)


@pytest.fixture
def mock_client() -> BitbucketClient:
    """Create a mocked Bitbucket Server client."""
    client = _build_client(
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
    client = _build_client(page_size=custom_page_size)
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
    client = _build_client()

    assert client.page_size == DEFAULT_PAGE_SIZE


@pytest.mark.asyncio
async def test_configurable_rate_limit() -> None:
    """Test that rate limit is configurable."""
    custom_rate_limit = 2000
    custom_window = 7200

    client = _build_client(
        rate_limit=custom_rate_limit, rate_limit_window=custom_window
    )

    assert client.rate_limiter.max_rate == custom_rate_limit
    assert client.rate_limiter.time_period == custom_window


@pytest.mark.asyncio
async def test_rate_limit_uses_spec_defaults() -> None:
    """Test that provided rate limit values are applied (mirrors spec defaults)."""
    client = _build_client()

    assert client.rate_limiter.max_rate == SPEC_DEFAULT_RATE_LIMIT
    assert client.rate_limiter.time_period == SPEC_DEFAULT_RATE_LIMIT_WINDOW


@pytest.mark.asyncio
async def test_configurable_concurrency() -> None:
    """Test that max concurrent requests is configurable."""
    custom_concurrency = 50

    client = _build_client(max_concurrent_requests=custom_concurrency)

    assert client.max_concurrent_requests == custom_concurrency
    assert client.semaphore._value == custom_concurrency


@pytest.mark.asyncio
async def test_default_concurrency() -> None:
    """Test that default concurrency is used when not specified."""
    client = _build_client()

    assert client.max_concurrent_requests == DEFAULT_MAX_CONCURRENT_REQUESTS
    assert client.semaphore._value == DEFAULT_MAX_CONCURRENT_REQUESTS


@pytest.mark.asyncio
async def test_project_filtering_with_prefix_regex() -> None:
    """Test project filtering with prefix regex pattern."""
    regex = re.compile("^PROD-.*")

    assert BitbucketClient._should_include_project("PROD-123", regex) is True
    assert BitbucketClient._should_include_project("PROD-ABC", regex) is True
    assert BitbucketClient._should_include_project("DEV-123", regex) is False
    assert BitbucketClient._should_include_project("TEST-ABC", regex) is False


@pytest.mark.asyncio
async def test_project_filtering_with_suffix_regex() -> None:
    """Test project filtering with suffix regex pattern."""
    regex = re.compile(".*-PROD$")

    assert BitbucketClient._should_include_project("PROJECT-PROD", regex) is True
    assert BitbucketClient._should_include_project("TEAM-PROD", regex) is True
    assert BitbucketClient._should_include_project("PROJECT-DEV", regex) is False
    assert BitbucketClient._should_include_project("TEAM-TEST", regex) is False


@pytest.mark.asyncio
async def test_project_filtering_with_combined_regex() -> None:
    """Test project filtering with combined prefix and suffix regex."""
    regex = re.compile("^TEAM-.*-PROD$")

    assert BitbucketClient._should_include_project("TEAM-APP-PROD", regex) is True
    assert BitbucketClient._should_include_project("TEAM-API-PROD", regex) is True
    assert BitbucketClient._should_include_project("TEAM-APP-DEV", regex) is False
    assert BitbucketClient._should_include_project("PROJECT-APP-PROD", regex) is False
    assert BitbucketClient._should_include_project("PROJECT-APP-DEV", regex) is False


@pytest.mark.asyncio
async def test_project_filtering_disabled_by_default() -> None:
    """Test that project filtering is disabled when no patterns are provided."""
    assert BitbucketClient._should_include_project("ANY-PROJECT", None) is True
    assert BitbucketClient._should_include_project("ANOTHER-ONE", None) is True
    assert BitbucketClient._should_include_project("TEST", None) is True


@pytest.mark.asyncio
async def test_project_filtering_logic_with_regex() -> None:
    """Test that project filtering logic works correctly with regex."""
    regex = re.compile("^PROD-.*")

    test_projects = [
        {"key": "PROD-123", "name": "Production 123"},
        {"key": "DEV-456", "name": "Development 456"},
        {"key": "PROD-789", "name": "Production 789"},
        {"key": "TEST-001", "name": "Test 001"},
    ]

    filtered = [
        p
        for p in test_projects
        if BitbucketClient._should_include_project(p["key"], regex)
    ]

    assert len(filtered) == 2
    assert all(p["key"].startswith("PROD-") for p in filtered)
    assert filtered[0]["key"] == "PROD-123"
    assert filtered[1]["key"] == "PROD-789"


@pytest.mark.asyncio
async def test_parallel_pr_fetching_uses_semaphore() -> None:
    """Test that PR fetching uses semaphore for concurrency control."""
    max_concurrent = 5
    client = _build_client(max_concurrent_requests=max_concurrent)

    assert client.semaphore._value == max_concurrent
    assert client.max_concurrent_requests == max_concurrent


@asynccontextmanager
async def mock_cache() -> AsyncGenerator[None, None]:
    """Patch ocean's cache provider so cache_iterator_result-decorated methods work in tests."""
    cache_provider = AsyncMock()
    cache_provider.get.return_value = None
    with patch("port_ocean.utils.cache.ocean") as mock_ocean:
        mock_ocean.app.cache_provider = cache_provider
        yield


@pytest.mark.asyncio
async def test_create_regex_from_project_keys_exact_match() -> None:
    """Test that _create_regex_from_project_keys produces an exact-match pattern (anchored at both ends)."""
    client = _build_client()
    regex = client._create_regex_from_project_keys({"PROJ-A", "PROJ-B"})

    assert regex.match("PROJ-A") is not None
    assert regex.match("PROJ-B") is not None
    assert regex.match("PROJ-C") is None
    assert regex.match("PROJ-A-EXTRA") is None
    assert regex.match("MY-PROJ-A") is None


@pytest.mark.asyncio
async def test_create_regex_from_project_keys_escapes_special_chars() -> None:
    """Test that special regex characters in project keys are properly escaped."""
    client = _build_client()
    regex = client._create_regex_from_project_keys({"PROJ.KEY", "PROJ+ONE"})

    assert regex.match("PROJ.KEY") is not None
    assert regex.match("PROJxKEY") is None
    assert regex.match("PROJ+ONE") is not None


@pytest.mark.asyncio
async def test_get_projects_with_specific_filter(mock_client: BitbucketClient) -> None:
    """Test get_projects with a projects_filter set returns only matching projects."""
    batches = [
        [
            {"key": "PROJ-A", "name": "Project A"},
            {"key": "PROJ-B", "name": "Project B"},
            {"key": "DEV-C", "name": "Dev C"},
        ]
    ]

    async def mock_get_all_projects() -> AsyncGenerator[list[dict[str, Any]], None]:
        for batch in batches:
            yield batch

    mock_client._get_all_projects = mock_get_all_projects  # type: ignore[method-assign]

    results: list[dict[str, Any]] = []
    async with mock_cache():
        async for batch in mock_client.get_projects(projects_filter={"PROJ-A", "DEV-C"}):
            results.extend(batch)

    assert len(results) == 2
    assert {p["key"] for p in results} == {"PROJ-A", "DEV-C"}


@pytest.mark.asyncio
async def test_get_projects_with_regex_filter(mock_client: BitbucketClient) -> None:
    """Test get_projects with a project_filter_regex returns only matching projects."""
    batches = [
        [
            {"key": "PROJ-A", "name": "Project A"},
            {"key": "PROJ-B", "name": "Project B"},
            {"key": "DEV-C", "name": "Dev C"},
        ]
    ]

    async def mock_get_all_projects() -> AsyncGenerator[list[dict[str, Any]], None]:
        for batch in batches:
            yield batch

    mock_client._get_all_projects = mock_get_all_projects  # type: ignore[method-assign]

    results: list[dict[str, Any]] = []
    async with mock_cache():
        async for batch in mock_client.get_projects(project_filter_regex="^PROJ-.*"):
            results.extend(batch)

    assert len(results) == 2
    assert all(p["key"].startswith("PROJ-") for p in results)


@pytest.mark.asyncio
async def test_get_projects_both_filters_apply_and_logic(
    mock_client: BitbucketClient,
) -> None:
    """Test get_projects with both projects_filter and project_filter_regex uses AND logic."""
    batches = [
        [
            {"key": "PROJ-A", "name": "Project A"},
            {"key": "PROJ-B", "name": "Project B"},
            {"key": "DEV-C", "name": "Dev C"},
            {"key": "DEV-D", "name": "Dev D"},
        ]
    ]

    async def mock_get_all_projects() -> AsyncGenerator[list[dict[str, Any]], None]:
        for batch in batches:
            yield batch

    mock_client._get_all_projects = mock_get_all_projects  # type: ignore[method-assign]

    results: list[dict[str, Any]] = []
    async with mock_cache():
        async for batch in mock_client.get_projects(
            projects_filter={"PROJ-A", "DEV-C"},
            project_filter_regex="^PROJ-.*",
        ):
            results.extend(batch)

    assert len(results) == 1
    assert results[0]["key"] == "PROJ-A"


@pytest.mark.asyncio
async def test_get_projects_no_filter_returns_all(mock_client: BitbucketClient) -> None:
    """Test that get_projects with no filters yields all projects."""
    batches = [
        [
            {"key": "PROJ-A", "name": "Project A"},
            {"key": "DEV-B", "name": "Dev B"},
            {"key": "TEST-C", "name": "Test C"},
        ]
    ]

    async def mock_get_all_projects() -> AsyncGenerator[list[dict[str, Any]], None]:
        for batch in batches:
            yield batch

    mock_client._get_all_projects = mock_get_all_projects  # type: ignore[method-assign]

    results: list[dict[str, Any]] = []
    async with mock_cache():
        async for batch in mock_client.get_projects():
            results.extend(batch)

    assert len(results) == 3


@pytest.mark.asyncio
async def test_project_filter_regex_match_anchors_at_start_only() -> None:
    """
    Document that project_filter_regex uses re.match(), which anchors at the start only.
    Users must add a trailing $ to enforce end anchoring.
    """
    regex_no_end_anchor = re.compile("PROD")
    assert BitbucketClient._should_include_project("PROD", regex_no_end_anchor) is True
    assert BitbucketClient._should_include_project("PRODUCTION", regex_no_end_anchor) is True
    assert BitbucketClient._should_include_project("MY-PROD", regex_no_end_anchor) is False

    regex_exact = re.compile("^PROD$")
    assert BitbucketClient._should_include_project("PROD", regex_exact) is True
    assert BitbucketClient._should_include_project("PRODUCTION", regex_exact) is False
    assert BitbucketClient._should_include_project("MY-PROD", regex_exact) is False
