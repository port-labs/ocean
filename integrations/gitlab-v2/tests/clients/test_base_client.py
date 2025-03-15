from typing import Any, AsyncGenerator, AsyncIterator
from unittest.mock import MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from clients.gitlab_client import GitLabClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "gitlab_host": "https://gitlab.example.com",
            "gitlab_token": "test-token",
        }
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


# Simple async generator function for mocking
async def async_mock_generator(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


@pytest.mark.asyncio
class TestGitLabClient:
    @pytest.fixture
    def client(self) -> GitLabClient:
        """Initialize GitLab client with test configuration"""
        return GitLabClient("https://gitlab.example.com", "test-token")

    async def test_get_projects(self, client: GitLabClient) -> None:
        """Test project fetching delegates to GraphQL client and handles nested fields."""
        # Arrange
        mock_projects: list[dict[str, Any]] = [
            {"id": "1", "name": "Test Project", "labels": {}}
        ]
        mock_labels: list[dict[str, Any]] = [{"id": "label1", "title": "Bug"}]

        # Mock field iterator yielding labels
        async def mock_field_iterator() -> (
            AsyncIterator[tuple[str, list[dict[str, Any]]]]
        ):
            yield "labels", mock_labels  # First page
            yield "labels", []

        # Mock get_resource to yield (projects, iterators)
        mock_iterators = [mock_field_iterator()]
        mock_response = [(mock_projects, mock_iterators)]  # Single batch with iterator

        with patch.object(
            client.graphql,
            "get_resource",
            return_value=async_mock_generator(mock_response),
        ) as mock_get_resource:
            # Act
            async for batch in client.get_projects():
                results: list[dict[str, Any]] = []

                results.extend(batch)

            # Assert
            assert len(results) == 1  # Only one project
            assert results[0]["name"] == "Test Project"
            assert results[0]["labels"]["nodes"] == mock_labels  # Nested field updated
            mock_get_resource.assert_called_once_with("projects")

    async def test_get_groups(self, client: GitLabClient) -> None:
        """Test group fetching delegates to REST client"""
        # Arrange
        mock_groups: list[dict[str, Any]] = [{"id": 1, "name": "Test Group"}]

        # Use a context manager for patching
        with patch.object(
            client.rest,
            "get_resource",
            return_value=async_mock_generator([mock_groups]),
        ) as mock_get_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_groups():
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["name"] == "Test Group"
            mock_get_resource.assert_called_once_with(
                "groups", params={"min_access_level": 30, "all_available": True}
            )

    async def test_get_group_resource(self, client: GitLabClient) -> None:
        """Test group resource fetching delegates to REST client"""
        # Arrange
        mock_issues: list[dict[str, Any]] = [{"id": 1, "title": "Test Issue"}]
        group: dict[str, str] = {"id": "123"}

        # Use a context manager for patching
        with patch.object(
            client.rest,
            "get_group_resource",
            return_value=async_mock_generator([mock_issues]),
        ) as mock_get_group_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_group_resource(
                [group], "issues"
            ):  # Changed to pass list of groups
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["title"] == "Test Issue"
            mock_get_group_resource.assert_called_once_with("123", "issues")
