from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

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
                "groups", params={"min_access_level": 30, "all_available": True}
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
        """Test file search in specific repositories"""
        # Arrange
        raw_files: list[dict[str, Any]] = [
            {"path": "test.json", "data": '{"key": "value"}', "project_id": "123"}
        ]
        repos = ["group/project"]
        pattern = "*.json"

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([raw_files]),
        ):
            with patch.object(
                client, "get_file_content", return_value='{"key": "value"}'
            ):  # Mock full content
                results: list[dict[str, Any]] = []
                async for batch in client.search_files(pattern, repositories=repos):
                    results.extend(batch)
                assert len(results) == 1
                assert results[0]["path"] == "test.json"
                assert results[0]["content"] == {"key": "value"}

    async def test_search_files_in_groups(self, client: GitLabClient) -> None:
        """Test file search across all groups"""
        # Arrange
        mock_groups: list[dict[str, Any]] = [{"id": "1", "name": "Group1"}]
        raw_files: list[dict[str, Any]] = [
            {"path": "test.yaml", "data": "key: value", "project_id": "123"}
        ]
        pattern = "*.yaml"

        with patch.object(
            client, "get_groups", return_value=async_mock_generator([mock_groups])
        ):
            with patch.object(
                client.rest,
                "get_paginated_group_resource",
                return_value=async_mock_generator([raw_files]),
            ):
                with patch.object(
                    client, "get_file_content", return_value="key: value"
                ):  # Mock full content
                    results: list[dict[str, Any]] = []
                    async for batch in client.search_files(pattern):
                        results.extend(batch)
                    assert len(results) == 1
                    assert results[0]["path"] == "test.yaml"
                    assert results[0]["content"] == {"key": "value"}  # Parsed YAML

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

    async def test_get_project(self, client: GitLabClient) -> None:
        """Test fetching a single project by path"""
        project_path = "group/project"
        mock_project = {
            "id": "123",
            "path_with_namespace": project_path,
            "default_branch": "main",
        }
        with patch.object(
            client.rest,
            "get_resource",
            AsyncMock(return_value=mock_project),
        ) as mock_get_resource:
            result = await client.get_project(project_path)
            assert result["id"] == "123"
            assert result["path_with_namespace"] == project_path
            mock_get_resource.assert_called_once_with("projects/group%2Fproject")

    async def test_file_exists(self, client: GitLabClient) -> None:
        """Test checking if a file exists in a project"""
        project_id = "123"
        scope = "blobs"
        query = "test.txt"
        mock_response = [{"path": "test.txt"}]  # Non-empty response means exists
        with patch.object(
            client.rest,
            "get_resource",
            AsyncMock(return_value=mock_response),
        ) as mock_get_resource:
            exists = await client.file_exists(project_id, scope, query)
            assert exists is True
            mock_get_resource.assert_called_once_with(
                "projects/123/search", params={"scope": "blobs", "search": "test.txt"}
            )

        # Test non-existent file
        with patch.object(
            client.rest,
            "get_resource",
            AsyncMock(return_value=[]),  # Empty response means doesn't exist
        ) as mock_get_resource:
            exists = await client.file_exists(project_id, scope, query)
            assert exists is False

    async def test_get_repository_tree(self, client: GitLabClient) -> None:
        """Test fetching repository tree (folders only) for a project"""
        project = {"path_with_namespace": "group/project"}
        path = "src"
        ref = "main"
        mock_tree = [
            {"type": "tree", "name": "folder1"},
            {"type": "blob", "name": "file.txt"},
            {"type": "tree", "name": "folder2"},
        ]
        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([mock_tree]),
        ) as mock_get_paginated:
            results = []
            async for batch in client.get_repository_tree(project, path, ref):
                results.extend(batch)

            assert len(results) == 2
            assert results[0]["folder"]["name"] == "folder1"
            assert results[1]["folder"]["name"] == "folder2"
            assert all(r["repo"] == project for r in results)
            assert all(r["__branch"] == ref for r in results)
            mock_get_paginated.assert_called_once_with(
                "group/project",
                "repository/tree",
                {"ref": "main", "path": "src", "recursive": True, "per_page": 100},
            )

    async def test_search_folders(self, client: GitLabClient) -> None:
        """Test searching folders across repositories"""
        repos = ["group/project1", "group/project2"]
        path = "src"
        branch = "develop"
        mock_project1 = {
            "id": "1",
            "path_with_namespace": "group/project1",
            "default_branch": "main",
        }
        mock_project2 = {
            "id": "2",
            "path_with_namespace": "group/project2",
            "default_branch": "main",
        }
        mock_tree = [
            {"type": "tree", "name": "folder1"},
            {"type": "blob", "name": "file.txt"},
        ]
        with patch.object(
            client, "get_project", AsyncMock(side_effect=[mock_project1, mock_project2])
        ) as mock_get_project:
            with patch.object(
                client.rest,
                "get_paginated_project_resource",
                side_effect=[
                    async_mock_generator([mock_tree]),
                    async_mock_generator([mock_tree]),
                ],
            ) as mock_get_paginated:
                results = []
                async for batch in client.search_folders(path, repos, branch):
                    results.extend(batch)

                assert len(results) == 2
                assert results[0]["folder"]["name"] == "folder1"
                assert results[0]["repo"] == mock_project1
                assert results[0]["__branch"] == "develop"
                assert results[1]["repo"] == mock_project2
                assert results[1]["__branch"] == "develop"
                mock_get_project.assert_any_call("group/project1")
                mock_get_project.assert_any_call("group/project2")
                mock_get_paginated.assert_any_call(
                    "group/project1",
                    "repository/tree",
                    {
                        "ref": "develop",
                        "path": "src",
                        "recursive": True,
                        "per_page": 100,
                    },
                )
                mock_get_paginated.assert_any_call(
                    "group/project2",
                    "repository/tree",
                    {
                        "ref": "develop",
                        "path": "src",
                        "recursive": True,
                        "per_page": 100,
                    },
                )
