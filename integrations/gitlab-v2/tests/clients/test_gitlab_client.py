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
        group: dict[str, str] = {"id": "123"}

        # Use a context manager for patching
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
            mock_send_request.assert_called_once_with(
                "GET", f"groups/{group_id}", params=client.DEFAULT_PARAMS
            )

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
            {"id": 1, "username": "user1", "name": "User One"},
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
            mock_get_members.assert_called_once_with("456", True)

    async def test_enrich_batch(self, client: GitLabClient) -> None:
        """Test the _enrich_batch method"""
        # Arrange
        batch = [
            {"id": 1, "name": "Project 1"},
            {"id": 2, "name": "Project 2"},
        ]

        async def mock_enrich_func(
            project: dict[str, Any]
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            project["enriched"] = True
            yield [project]

        # Act
        result = await client._enrich_batch(batch, mock_enrich_func, max_concurrent=1)

        # Assert
        assert len(result) == 2
        assert result[0]["enriched"] is True
        assert result[1]["enriched"] is True
