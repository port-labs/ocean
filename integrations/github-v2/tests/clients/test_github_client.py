from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context import event
from port_ocean.context.event import EventContext

from github.clients.github_client import GitHubClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "github_host": "https://api.github.com",
            "github_token": "test-token",
        }
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


async def async_mock_generator(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


@pytest.mark.asyncio
class TestGitHubClient:
    @pytest.fixture
    def client(self) -> GitHubClient:
        """Initialize GitHub client with test configuration"""
        return GitHubClient("https://api.github.com", "test-token")

    async def test_get_repository(self, client: GitHubClient) -> None:
        """Test fetching a single repository"""
        # Arrange
        repo_path = "owner/repo"
        mock_repo = {
            "id": 123,
            "full_name": "owner/repo",
            "name": "repo",
            "default_branch": "main",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_repo)
        ) as mock_send_request:
            # Act
            result = await client.get_repository(repo_path)

            # Assert
            assert result == mock_repo
            mock_send_request.assert_called_once_with("GET", "repos/owner%2Frepo")

    async def test_get_organizations(self, client: GitHubClient) -> None:
        """Test fetching organizations"""
        # Arrange
        mock_orgs = [{"id": 1, "login": "test-org"}]

        with patch.object(
            client.rest,
            "get_paginated_resource",
            return_value=async_mock_generator([mock_orgs]),
        ) as mock_get_resource:
            # Act
            results = []
            async for batch in client.get_organizations():
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["login"] == "test-org"
            mock_get_resource.assert_called_once_with("user/orgs", params=None)


    async def test_get_pull_request(self, client: GitHubClient) -> None:
        """Test fetching a single pull request"""
        # Arrange
        repo_path = "owner/repo"
        pr_number = 123
        mock_pr = {
            "id": 456,
            "number": pr_number,
            "title": "Test PR",
            "state": "open",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_pr)
        ) as mock_send_request:
            # Act
            result = await client.get_pull_request(repo_path, pr_number)

            # Assert
            assert result == mock_pr
            mock_send_request.assert_called_once_with(
                "GET", f"repos/{repo_path}/pulls/{pr_number}"
            )

    async def test_get_issue(self, client: GitHubClient) -> None:
        """Test fetching a single issue"""
        # Arrange
        repo_path = "owner/repo"
        issue_number = 789
        mock_issue = {
            "id": 101,
            "number": issue_number,
            "title": "Test Issue",
            "state": "open",
        }

        with patch.object(
            client.rest, "send_api_request", AsyncMock(return_value=mock_issue)
        ) as mock_send_request:
            # Act
            result = await client.get_issue(repo_path, issue_number)

            # Assert
            assert result == mock_issue
            mock_send_request.assert_called_once_with(
                "GET", f"repos/{repo_path}/issues/{issue_number}"
            )

    async def test_get_file_content(self, client: GitHubClient) -> None:
        """Test fetching file content"""
        # Arrange
        repo_path = "owner/repo"
        file_path = "README.md"
        ref = "main"
        mock_content = "# Test README"

        with patch.object(
            client.rest,
            "get_file_content",
            return_value=mock_content,
        ) as mock_get_file:
            # Act
            result = await client.get_file_content(repo_path, file_path, ref)

            # Assert
            assert result == mock_content
            mock_get_file.assert_called_once_with(repo_path, file_path, ref)

    async def test_get_repository_resource(self, client: GitHubClient) -> None:
        """Test fetching repository resources"""
        # Arrange
        mock_repos = [{"id": 1, "full_name": "owner/repo"}]
        mock_issues = [{"id": 1, "title": "Test Issue"}]

        with patch.object(
            client.rest,
            "get_paginated_repo_resource",
            return_value=async_mock_generator([mock_issues]),
        ) as mock_get_resource:
            # Act
            results = []
            async for batch in client.get_repository_resource(
                mock_repos, "issues", max_concurrent=1
            ):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["title"] == "Test Issue"

    async def test_get_organization_resource(self, client: GitHubClient) -> None:
        """Test fetching organization resources"""
        # Arrange
        mock_orgs = [{"id": 1, "login": "test-org"}]
        mock_teams = [{"id": 1, "name": "Test Team"}]

        with patch.object(
            client.rest,
            "get_paginated_org_resource",
            return_value=async_mock_generator([mock_teams]),
        ) as mock_get_resource:
            # Act
            results = []
            async for batch in client.get_organization_resource(
                mock_orgs, "teams", max_concurrent=1
            ):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["name"] == "Test Team"
