import pytest
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock, patch
from clients.base_client import GitLabClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


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
        """Test project fetching delegates to GraphQL client with optional params"""
        # Arrange
        mock_projects: list[dict[str, Any]] = [
            {"id": 1, "name": "Test Project", "repository": {"blobs": {"nodes": []}}}
        ]
        test_params = {"filePaths": ["test.txt"]}

        with patch.object(
            client.graphql,
            "get_resource",
            return_value=async_mock_generator([mock_projects]),
        ) as mock_get_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_projects(params=test_params):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["name"] == "Test Project"
            mock_get_resource.assert_called_once_with("projects", params=test_params)

    async def test_get_groups(self, client: GitLabClient) -> None:
        """Test group fetching delegates to REST client"""
        # Arrange
        mock_groups: list[dict[str, Any]] = [{"id": 1, "name": "Test Group"}]

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

        with patch.object(
            client.rest,
            "get_group_resource",
            return_value=async_mock_generator([mock_issues]),
        ) as mock_get_group_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_group_resource(group, "issues"):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["title"] == "Test Issue"
            mock_get_group_resource.assert_called_once_with("123", "issues", None)

    async def test_get_project_resource(self, client: GitLabClient) -> None:
        """Test project resource fetching delegates to REST client"""
        # Arrange
        mock_files: list[dict[str, Any]] = [{"path": "test.txt", "data": "content"}]
        project_path = "group/project"

        with patch.object(
            client.rest,
            "get_project_resource",
            return_value=async_mock_generator([mock_files]),
        ) as mock_get_project_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_project_resource(project_path, "search"):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["path"] == "test.txt"
            mock_get_project_resource.assert_called_once_with(
                "group%2Fproject", "search", None
            )

    async def test_search_files_in_repos(self, client: GitLabClient) -> None:
        """Test file search in specific repositories"""
        # Arrange
        raw_files: list[dict[str, Any]] = [{"path": "test.json", "data": '{"key": "value"}'}]
        repos = ["group/project"]
        pattern = "*.json"

        with patch.object(
            client.rest,
            "get_project_resource",
            return_value=async_mock_generator([raw_files]),
        ):
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.search_files(pattern, repositories=repos):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["path"] == "test.json"
            assert results[0]["data"] == {"key": "value"}  # Parsed JSON

    async def test_search_files_in_groups(self, client: GitLabClient) -> None:
        """Test file search across all groups"""
        # Arrange
        mock_groups: list[dict[str, Any]] = [{"id": "1", "name": "Group1"}]
        raw_files: list[dict[str, Any]] = [{"path": "test.yaml", "data": "key: value"}]
        pattern = "*.yaml"

        with patch.object(
            client,
            "get_groups",
            return_value=async_mock_generator([mock_groups]),
        ):
            with patch.object(
                client.rest,
                "get_group_resource",
                return_value=async_mock_generator([raw_files]),
            ):
                # Act
                results: list[dict[str, Any]] = []
                async for batch in client.search_files(pattern):
                    results.extend(batch)

                # Assert
                assert len(results) == 1
                assert results[0]["path"] == "test.yaml"
                assert results[0]["data"] == {"key": "value"}  # Parsed YAML

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