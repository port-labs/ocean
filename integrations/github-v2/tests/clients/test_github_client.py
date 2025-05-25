from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

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

    async def test_get_repositories(self, client: GitHubClient) -> None:
        """Test fetching repositories"""
        # Arrange
        mock_repos = [
            {
                "id": 1,
                "full_name": "owner/repo1",
                "name": "repo1",
            }
        ]

        with patch.object(
            client.rest,
            "get_paginated_resource",
            return_value=async_mock_generator([mock_repos]),
        ) as mock_get_resource:
            # Act
            results = []
            async for batch in client.get_repositories():
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["name"] == "repo1"
            mock_get_resource.assert_called_once_with("user/repos", params={})

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

    async def test_get_team_members(self, client: GitHubClient) -> None:
        """Test fetching team members"""
        # Arrange
        org_name = "test-org"
        team_slug = "test-team"
        mock_members = [
            {"id": 1, "login": "user1"},
            {"id": 2, "login": "user2"},
        ]

        with patch.object(
            client.rest,
            "get_paginated_resource",
            return_value=async_mock_generator([mock_members]),
        ) as mock_get_resource:
            # Act
            results = []
            async for batch in client.get_team_members(org_name, team_slug):
                results.extend(batch)

            # Assert
            assert len(results) == 2
            assert results[0]["login"] == "user1"
            assert results[1]["login"] == "user2"
            mock_get_resource.assert_called_once_with(f"orgs/{org_name}/teams/{team_slug}/members")

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


# tests/clients/test_rest_client.py
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from github.clients.rest_client import RestClient


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


@pytest.mark.asyncio
class TestRestClient:
    @pytest.fixture
    def client(self) -> RestClient:
        """Initialize REST client with test configuration"""
        return RestClient("https://api.github.com", "test-token")

    async def test_get_paginated_resource(self, client: RestClient) -> None:
        """Test paginated resource fetching"""
        # Arrange
        mock_response1 = MagicMock()
        mock_response1.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response1.headers = {}

        mock_response2 = MagicMock()
        mock_response2.json.return_value = [{"id": 3}]
        mock_response2.headers = {}

        mock_response3 = MagicMock()
        mock_response3.json.return_value = []
        mock_response3.headers = {}

        with patch.object(
            client,
            "send_api_request",
            AsyncMock(side_effect=[mock_response1, mock_response2, mock_response3]),
        ) as mock_send:
            with patch.object(
                client,
                "get_page_links",
                AsyncMock(side_effect=[
                    {"next": "https://api.github.com/repos?page=2"},
                    {"next": "https://api.github.com/repos?page=3"},
                    {}
                ]),
            ):
                # Act
                results = []
                async for batch in client.get_paginated_resource("repos"):
                    results.extend(batch)

                # Assert
                assert len(results) == 3
                assert results[0]["id"] == 1
                assert results[1]["id"] == 2
                assert results[2]["id"] == 3

    async def test_get_file_content(self, client: RestClient) -> None:
        """Test fetching file content"""
        # Arrange
        repo_path = "owner/repo"
        file_path = "README.md"
        ref = "main"
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": "IyBUZXN0IFJFQURNRQ==",  # Base64 encoded "# Test README"
            "encoding": "base64",
        }

        with patch.object(
            client,
            "send_api_request",
            AsyncMock(return_value=mock_response),
        ) as mock_send:
            # Act
            result = await client.get_file_content(repo_path, file_path, ref)

            # Assert
            assert result == "# Test README"
            mock_send.assert_called_once_with(
                "GET",
                "repos/owner/repo/contents/README.md",
                params={"ref": "main"},
            )

    async def test_get_page_links(self, client: RestClient) -> None:
        """Test parsing GitHub pagination links"""
        # Arrange
        mock_response = MagicMock()
        mock_response.headers = {
            "Link": '<https://api.github.com/repos?page=2>; rel="next", <https://api.github.com/repos?page=10>; rel="last"'
        }

        # Act
        links = await client.get_page_links(mock_response)

        # Assert
        assert links["next"] == "https://api.github.com/repos?page=2"
        assert links["last"] == "https://api.github.com/repos?page=10"

    async def test_get_paginated_repo_resource(self, client: RestClient) -> None:
        """Test fetching paginated repository resources"""
        # Arrange
        repo_path = "owner/repo"
        resource_type = "issues"
        mock_issues = [{"id": 1, "title": "Issue 1"}]

        with patch.object(
            client,
            "get_paginated_resource",
            return_value=self._async_generator([mock_issues]),
        ) as mock_get_paginated:
            # Act
            results = []
            async for batch in client.get_paginated_repo_resource(
                repo_path, resource_type
            ):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["title"] == "Issue 1"
            mock_get_paginated.assert_called_once_with(
                "repos/owner/repo/issues", params=None
            )

    async def test_get_paginated_org_resource(self, client: RestClient) -> None:
        """Test fetching paginated organization resources"""
        # Arrange
        org_name = "test-org"
        resource_type = "teams"
        mock_teams = [{"id": 1, "name": "Team 1"}]

        with patch.object(
            client,
            "get_paginated_resource",
            return_value=self._async_generator([mock_teams]),
        ) as mock_get_paginated:
            # Act
            results = []
            async for batch in client.get_paginated_org_resource(
                org_name, resource_type
            ):
                results.extend(batch)

            # Assert
            assert len(results) == 1
            assert results[0]["name"] == "Team 1"
            mock_get_paginated.assert_called_once_with(
                f"orgs/{org_name}/{resource_type}", params=None
            )

    @staticmethod
    async def _async_generator(items: list[Any]):
        """Helper to create async generator"""
        for item in items:
            yield item
