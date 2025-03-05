import pytest
from unittest.mock import MagicMock
from clients.base_client import GitLabClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_ocean_context():
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
async def async_mock_generator(items):
    for item in items:
        yield item


@pytest.mark.asyncio
class TestGitLabClient:
    @pytest.fixture
    def client(self):
        """Initialize GitLab client with test configuration"""
        return GitLabClient("https://gitlab.example.com", "test-token")

    async def test_get_projects(self, client):
        """Test project fetching delegates to GraphQL client"""
        # Arrange
        mock_projects = [{"id": 1, "name": "Test Project"}]
        client.graphql.get_resource = MagicMock(
            return_value=async_mock_generator([mock_projects])
        )

        # Act
        results = []
        async for batch in client.get_projects():
            results.extend(batch)

        # Assert
        assert len(results) == 1
        assert results[0]["name"] == "Test Project"
        client.graphql.get_resource.assert_called_once_with("projects")

    async def test_get_groups(self, client):
        """Test group fetching delegates to REST client"""
        # Arrange
        mock_groups = [{"id": 1, "name": "Test Group"}]
        client.rest.get_resource = MagicMock(
            return_value=async_mock_generator([mock_groups])
        )

        # Act
        results = []
        async for batch in client.get_groups():
            results.extend(batch)

        # Assert
        assert len(results) == 1
        assert results[0]["name"] == "Test Group"
        client.rest.get_resource.assert_called_once_with(
            "groups", params={"min_access_level": 30, "all_available": True}
        )

    async def test_get_group_resource(self, client):
        """Test group resource fetching delegates to REST client"""
        # Arrange
        mock_issues = [{"id": 1, "title": "Test Issue"}]
        group = {"id": "123"}
        client.rest.get_group_resource = MagicMock(
            return_value=async_mock_generator([mock_issues])
        )

        # Act
        results = []
        async for batch in client.get_group_resource(group, "issues"):
            results.extend(batch)

        # Assert
        assert len(results) == 1
        assert results[0]["title"] == "Test Issue"
        client.rest.get_group_resource.assert_called_once_with("123", "issues")
