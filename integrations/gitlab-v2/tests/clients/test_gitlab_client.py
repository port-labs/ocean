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
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
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

        # Use a context manager for patching
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
        group: list[dict[str, Any]] = [{"id": "123"}]

        # Use a context manager for patching
        with patch.object(
            client.rest,
            "get_paginated_group_resource",
            return_value=async_mock_generator([mock_issues]),
        ) as mock_get_group_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_groups_resource(
                group, "issues"
            ):  # Changed to pass list of groups
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["title"] == "Test Issue"
            mock_get_group_resource.assert_called_once_with("123", "issues", None)

    async def test_get_group(self, client: GitLabClient) -> None:
        """Test fetching a single group by ID"""
        # Arrange
        group_id = 456
        mock_group = {
            "id": group_id,
            "name": "Test Group",
            "path": "test-group",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_group)
        ) as mock_send_request:
            # Act
            result = await client.get_group(group_id)

            # Assert
            assert result == mock_group
            mock_send_request.assert_called_once_with("GET", f"groups/{group_id}")

    async def test_get_merge_request(self, client: GitLabClient) -> None:
        """Test fetching a single merge request by ID"""
        # Arrange
        project_id = 123
        merge_request_id = 789
        mock_merge_request = {
            "id": merge_request_id,
            "title": "Test Merge Request",
            "state": "opened",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_merge_request)
        ) as mock_send_request:
            # Act
            result = await client.get_merge_request(project_id, merge_request_id)

            # Assert
            assert result == mock_merge_request
            mock_send_request.assert_called_once_with(
                "GET", f"projects/{project_id}/merge_requests/{merge_request_id}"
            )

    async def test_get_issue(self, client: GitLabClient) -> None:
        """Test fetching a single issue by ID"""
        # Arrange
        project_id = 123
        issue_id = 101
        mock_issue = {
            "id": issue_id,
            "title": "Test Issue",
            "state": "opened",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_issue)
        ) as mock_send_request:
            # Act
            result = await client.get_issue(project_id, issue_id)

            # Assert
            assert result == mock_issue
            mock_send_request.assert_called_once_with(
                "GET", f"projects/{project_id}/issues/{issue_id}"
            )

    async def test_get_group_member(self, client: GitLabClient) -> None:
        """Test fetching a single group member by ID"""
        # Arrange
        group_id = 456
        member_id = 202
        mock_member = {
            "id": member_id,
            "username": "testuser",
            "name": "Test User",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_member)
        ) as mock_send_request:
            # Act
            result = await client.get_group_member(group_id, member_id)

            # Assert
            assert result == mock_member
            mock_send_request.assert_called_once_with(
                "GET", f"groups/{group_id}/members/{member_id}"
            )

    async def test_get_group_members(self, client: GitLabClient) -> None:
        """Test fetching group members with and without bot filtering"""
        # Arrange
        group_id = "456"
        mock_members = [
            {"id": 1, "username": "user1", "name": "User One"},
            {"id": 2, "username": "bot1", "name": "Bot One"},
            {"id": 3, "username": "user2", "name": "User Two"},
        ]

        with patch.object(
            client.rest,
            "get_paginated_group_resource",
            return_value=async_mock_generator([mock_members]),
        ) as mock_get_resource:
            # Act - with bot members
            results_with_bots = []
            async for batch in client.get_group_members(
                group_id, include_bot_members=True
            ):
                results_with_bots.extend(batch)

            # Assert - with bot members
            assert len(results_with_bots) == 3
            assert results_with_bots[0]["username"] == "user1"
            assert results_with_bots[1]["username"] == "bot1"
            assert results_with_bots[2]["username"] == "user2"
            mock_get_resource.assert_called_with(group_id, "members")

            # Reset mock and set up for the second test case
            mock_get_resource.reset_mock()
            mock_get_resource.return_value = async_mock_generator([mock_members])

            # Act - without bot members
            results_without_bots = []
            async for batch in client.get_group_members(
                group_id, include_bot_members=False
            ):
                results_without_bots.extend(batch)

            # Assert - without bot members
            assert len(results_without_bots) == 2
            assert results_without_bots[0]["username"] == "user1"
            assert results_without_bots[1]["username"] == "user2"
            mock_get_resource.assert_called_with(group_id, "members")

    async def test_enrich_group_with_members(self, client: GitLabClient) -> None:
        """Test enriching a group with its members"""
        # Arrange
        group = {"id": "456", "name": "Test Group"}
        mock_members = [
            {
                "id": 1,
                "username": "user1",
                "name": "User One",
                "email": "user1@example.com",
            },
            {"id": 2, "username": "user2", "name": "User Two"},
        ]

        with patch.object(
            client,
            "get_group_members",
            return_value=async_mock_generator([mock_members]),
        ) as mock_get_members:
            # Act
            result = await client.enrich_group_with_members(
                group, include_bot_members=True
            )

            # Assert
            assert result["id"] == "456"
            assert result["name"] == "Test Group"
            assert "__members" in result
            assert len(result["__members"]) == 2
            assert result["__members"][0]["username"] == "user1"
            assert result["__members"][1]["username"] == "user2"
            assert result["__members"][0]["email"] == "user1@example.com"
            assert result["__members"][1]["email"] is None
            mock_get_members.assert_called_once_with("456", True)

    async def test_enrich_batch(self, client: GitLabClient) -> None:
        """Test the _enrich_batch method"""
        # Arrange
        batch = [
            {"id": 1, "name": "Project 1"},
            {"id": 2, "name": "Project 2"},
        ]

        async def mock_enrich_func(project: dict[str, Any]) -> dict[str, Any]:
            project["enriched"] = True
            return project

        # Act
        result = await client._enrich_batch(batch, mock_enrich_func, max_concurrent=1)

        # Assert
        assert len(result) == 2
        assert result[0]["enriched"] is True
        assert result[1]["enriched"] is True

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
            "_search_files_in_repository",
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
                "_search_files_in_group",
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
            "send_api_request",
            AsyncMock(return_value=mock_project),
        ) as mock_send_request:
            result = await client.get_project(project_path)
            assert result["id"] == "123"
            assert result["path_with_namespace"] == project_path
            mock_send_request.assert_called_once_with("GET", "projects/group%2Fproject")

    async def test_file_exists(self, client: GitLabClient) -> None:
        """Test checking if a file exists in a project"""
        project_id = "123"
        scope = "blobs"
        query = "test.txt"
        mock_response = [{"path": "test.txt"}]  # Non-empty response means exists
        with patch.object(
            client.rest,
            "send_api_request",
            AsyncMock(return_value=mock_response),
        ) as mock_send_request:
            exists = await client.file_exists(project_id, scope, query)
            assert exists is True
            mock_send_request.assert_called_once_with(
                "GET",
                "projects/123/search",
                params={"scope": "blobs", "search": "test.txt"},
            )

        # Test non-existent file
        with patch.object(
            client.rest,
            "send_api_request",
            AsyncMock(return_value=[]),  # Empty response means doesn't exist
        ) as mock_send_request:
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
                {"ref": "main", "path": "src", "recursive": False},
            )

    async def test_get_repository_folders(self, client: GitLabClient) -> None:
        """Test searching folders in a single repository"""
        # Arrange
        repository = "group/project1"
        path = "src"
        branch = "develop"

        mock_project = {
            "id": "1",
            "path_with_namespace": "group/project1",
            "default_branch": "main",
        }

        mock_tree = [
            {"type": "tree", "name": "folder1"},
            {"type": "blob", "name": "file.txt"},
        ]

        with patch.object(
            client, "get_project", AsyncMock(return_value=mock_project)
        ) as mock_get_project:
            with patch.object(
                client.rest,
                "get_paginated_project_resource",
                return_value=async_mock_generator([mock_tree]),
            ) as mock_get_paginated:
                # Act
                results = []
                async for batch in client.get_repository_folders(
                    path, repository, branch
                ):
                    results.extend(batch)

                # Assert
                assert len(results) == 1  # Only one folder from mock_tree
                assert results[0]["folder"]["name"] == "folder1"
                assert results[0]["repo"] == mock_project
                assert results[0]["__branch"] == "develop"

                mock_get_project.assert_called_once_with("group/project1")
                mock_get_paginated.assert_called_once_with(
                    "group/project1",
                    "repository/tree",
                    {"ref": "develop", "path": "src", "recursive": False},
                )

    async def test_process_file_with_file_reference(self, client: GitLabClient) -> None:
        """Test that parsed file content with file:// reference fetches and resolves content."""
        # Arrange
        file = {
            "path": "config.yaml",
            "project_id": "123",
            "ref": "main",
        }
        mock_file_content = """
        key: value
        ref: file://other_file.txt
        """
        mock_referenced_content = "Referenced content"
        mock_file_data = {
            "content": mock_file_content,
            "path": "config.yaml",
        }
        expected_parsed_content = {
            "key": "value",
            "ref": mock_referenced_content,
        }

        with (
            patch.object(
                client.rest,
                "get_file_data",
                AsyncMock(return_value=mock_file_data),
            ) as mock_get_file_data,
            patch.object(
                client,
                "get_file_content",
                AsyncMock(return_value=mock_referenced_content),
            ) as mock_get_file_content,
        ):
            # Act
            result = await client._process_file(
                file, context="test_context", skip_parsing=False
            )

            # Assert
            assert result["path"] == "config.yaml"
            assert result["project_id"] == "123"
            assert result["content"] == expected_parsed_content
            mock_get_file_data.assert_called_once_with("123", "config.yaml", "main")
            mock_get_file_content.assert_called_once_with(
                "123", "other_file.txt", "main"
            )

    async def test_get_project_jobs(self, client: GitLabClient) -> None:
        """Test fetching project jobs"""
        # Arrange
        mock_projects = [{"id": 1, "name": "Test Project"}]
        mock_jobs = [{"id": 1, "name": "Test Job"}]

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([mock_jobs]),
        ) as mock_get_paginated:
            results = []
            async for batch in client.get_project_jobs(mock_projects):
                results.extend(batch)

            assert len(results) == 1
            assert results[0]["id"] == 1
            assert results[0]["name"] == "Test Job"
            mock_get_paginated.assert_called_once_with(
                "1", "jobs", params={"per_page": 100}
            )

    async def test_project_resource(self, client: GitLabClient) -> None:
        """Test project resource fetching delegates to REST client"""
        # Arrange
        mock_pipelines = [{"id": 1, "name": "Test Pipeline"}]
        mock_projects = [{"id": 1, "name": "Test Project"}]

        with patch.object(
            client.rest,
            "get_paginated_project_resource",
            return_value=async_mock_generator([mock_pipelines]),
        ) as mock_get_project_resource:
            # Act
            results: list[dict[str, Any]] = []
            async for batch in client.get_projects_resource(mock_projects, "pipelines"):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["id"] == 1
            assert results[0]["name"] == "Test Pipeline"
            mock_get_project_resource.assert_called_once_with("1", "pipelines")
