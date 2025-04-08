from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from gitlab.clients.gitlab_client import GitLabClient


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
        """Test project fetching and enrichment with languages and labels via REST."""
        # Arrange
        mock_projects = [
            {
                "id": "1",
                "name": "Test Project",
                "path_with_namespace": "test/test-project",
            }
        ]
        mock_languages = {"Python": 50.0, "JavaScript": 30.0}

        with (
            patch.object(client.rest, "get_paginated_resource") as mock_get_resource,
            patch.object(
                client.rest,
                "get_project_languages",
                AsyncMock(return_value=mock_languages),
            ) as mock_get_languages,
        ):

            # Mock get_resource to yield projects
            mock_get_resource.return_value = async_mock_generator([mock_projects])

            # Act
            results = []
            params = {"some": "param"}
            async for batch in client.get_projects(
                params=params,
                max_concurrent=1,
                include_languages=True,
            ):
                results.extend(batch)

            # Assert
            assert len(results) == 1  # One project in the batch
            assert results[0]["name"] == "Test Project"
            assert results[0]["__languages"] == mock_languages
            mock_get_languages.assert_called_once_with("test/test-project")

    async def test_get_groups(self, client: GitLabClient) -> None:
        """Test group fetching delegates to REST client"""
        # Arrange
        mock_groups: list[dict[str, Any]] = [{"id": 1, "name": "Test Group"}]

        with patch.object(
            client.rest,
            "get_paginated_resource",
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
                "groups",
                params={
                    "min_access_level": 30,
                    "all_available": True,
                    "top_level_only": False,
                },
            )

    async def test_get_groups_top_level_only(self, client: GitLabClient) -> None:
        """Test group fetching with top level only"""
        # Arrange
        mock_groups: list[dict[str, Any]] = [
            {"id": 1, "name": "Test Group", "parent_id": None},
        ]

        # Use a context manager for patching
        with patch.object(
            client.rest,
            "get_paginated_resource",
            return_value=async_mock_generator([mock_groups]),
        ) as mock_get_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_groups(top_level_only=True):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["name"] == "Test Group"
            assert results[0]["parent_id"] is None
            mock_get_resource.assert_called_once_with(
                "groups",
                params={
                    "min_access_level": 30,
                    "top_level_only": True,
                    "all_available": True,
                },
            )

    async def test_get_group_resource(self, client: GitLabClient) -> None:
        """Test group resource fetching delegates to REST client"""
        # Arrange
        mock_issues: list[dict[str, Any]] = [{"id": 1, "title": "Test Issue"}]
        group: dict[str, str] = {"id": "123"}

        with patch.object(
            client.rest,
            "get_paginated_group_resource",
            return_value=async_mock_generator([mock_issues]),
        ) as mock_get_group_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_groups_resource(
                [group], "issues"
            ):  # Changed to pass list of groups
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["title"] == "Test Issue"
            mock_get_group_resource.assert_called_once_with("123", "issues")

    async def test_search_files_in_repos(self, client: GitLabClient) -> None:
        """Test file search in specific repositories using scope and query via _search_in_repository"""
        processed_files = [
            {"path": "test.json", "project_id": "123", "content": {"key": "value"}}
        ]
        repos = ["group/project"]
        scope = "blobs"
        query = "test.json"
        with patch.object(
            client,
            "_search_in_repository",
            return_value=async_mock_generator([processed_files]),
        ) as mock_search_repo:
            with patch.object(
                client, "get_file_content", return_value='{"key": "value"}'
            ):
                results = []
                async for batch in client.search_files(
                    scope, query, repositories=repos, skip_parsing=False
                ):
                    results.extend(batch)
                assert len(results) == 1
                assert results[0]["path"] == "test.json"
                assert results[0]["content"] == {"key": "value"}
                mock_search_repo.assert_called_once_with(
                    "group/project", "blobs", "path:test.json", False
                )

    async def test_search_files_in_groups(self, client: GitLabClient) -> None:
        """Test file search across all groups using scope and query"""
        mock_groups = [{"id": "1", "name": "Group1"}]
        processed_files = [
            {"path": "test.yaml", "project_id": "123", "content": {"key": "value"}}
        ]
        scope = "blobs"
        query = "test.yaml"
        with patch.object(
            client, "get_groups", return_value=async_mock_generator([mock_groups])
        ):
            with patch.object(
                client,
                "_search_in_group",
                return_value=async_mock_generator([processed_files]),
            ) as mock_search_group:
                with patch.object(
                    client, "get_file_content", return_value="key: value"
                ):
                    results = []
                    async for batch in client.search_files(
                        scope, query, skip_parsing=False
                    ):
                        results.extend(batch)
                    assert len(results) == 1
                    assert results[0]["path"] == "test.yaml"
                    assert results[0]["content"] == {"key": "value"}
                    mock_search_group.assert_called_once_with(
                        "1", "blobs", "path:test.yaml", False
                    )

    async def test_get_file_content(self, client: GitLabClient) -> None:
        """Test fetching file content via REST"""
        # Arrange
        project_id = "123"
        file_path = "test.txt"
        mock_content = "Hello, World!"
        with patch.object(
            client.rest,
            "get_file_content",
            return_value=mock_content,
        ) as mock_get_file_content:
            # Act
            result = await client.get_file_content(project_id, file_path, "main")

            # Assert
            assert result == mock_content
            mock_get_file_content.assert_called_once_with(project_id, file_path, "main")
