from unittest.mock import AsyncMock, MagicMock

import pytest

from client import BitbucketClient


@pytest.fixture
def mock_client() -> BitbucketClient:
    """Create a mocked Bitbucket Server client."""
    client = BitbucketClient(
        base_url="https://bitbucket.example.com",
        username="test-user",
        password="test-password",
    )
    client = MagicMock(spec=BitbucketClient)
    return client


@pytest.mark.asyncio
async def test_get_projects(mock_client: BitbucketClient) -> None:
    """Test getting projects from Bitbucket Server."""
    # Arrange
    expected_projects = [{"id": 1, "key": "TEST", "name": "Test Project"}]
    mock_client.get_projects = AsyncMock(return_value=expected_projects)

    # Act
    projects = await mock_client.get_projects()

    # Assert
    assert projects == expected_projects
    mock_client.get_projects.assert_called_once()


@pytest.mark.asyncio
async def test_get_repositories(mock_client: BitbucketClient) -> None:
    """Test getting repositories from Bitbucket Server."""
    # Arrange
    project_key = "TEST"
    expected_repos = [{"id": 1, "name": "test-repo", "slug": "test-repo"}]
    mock_client.get_repositories = AsyncMock(return_value=expected_repos)

    # Act
    repos = await mock_client.get_repositories(project_key)

    # Assert
    assert repos == expected_repos
    mock_client.get_repositories.assert_called_once_with(project_key)


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client: BitbucketClient) -> None:
    """Test getting pull requests from Bitbucket Server."""
    # Arrange
    project_key = "TEST"
    repo_slug = "test-repo"
    expected_prs = [{"id": 1, "title": "Test PR", "state": "OPEN"}]
    mock_client.get_pull_requests = AsyncMock(return_value=expected_prs)

    # Act
    prs = await mock_client.get_pull_requests(project_key, repo_slug)

    # Assert
    assert prs == expected_prs
    mock_client.get_pull_requests.assert_called_once_with(project_key, repo_slug)
