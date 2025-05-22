import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from pytest_mock import MockerFixture

from github.client import (
    GithubClient,
    GithubAPIError,
)


@pytest.fixture
def mock_http_async_client(mocker: MockerFixture) -> AsyncMock:
    """Fixture to mock the http_async_client."""
    mock_client = AsyncMock()
    mocker.patch("github.client.http_async_client", mock_client)
    return mock_client


@pytest.fixture
def mock_response() -> MagicMock:
    """Fixture for a generic mock HTTP response."""
    response = MagicMock()
    response.headers = {}
    response.status_code = 200
    response.json = MagicMock(return_value={"key": "value"})
    response.text = '{"key": "value"}'
    # Make raise_for_status a regular MagicMock, we'll control its side_effect in tests
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def client() -> GithubClient:
    """Fixture for a GithubClient instance."""
    return GithubClient(token="test_token")


def test_github_client_initialization() -> None:
    client = GithubClient(
        token="fake_token",
        base_url="http://custom.api",
        api_version="v1",
        max_retries=5,
        backoff_factor=1.0,
    )
    assert client.token == "fake_token"
    assert client.base_url == "http://custom.api"
    assert client.base_headers["X-GitHub-Api-Version"] == "v1"
    assert client.max_retries == 5
    assert client.backoff_factor == 1.0


def test_github_client_initialization_empty_token() -> None:
    with pytest.raises(ValueError, match="GitHub token cannot be empty"):
        GithubClient(token="")


def test_github_client_from_env_success(mocker: MockerFixture) -> None:
    mocker.patch.dict(os.environ, {"TEST_GITHUB_TOKEN": "env_token"})
    client = GithubClient.from_env(key="TEST_GITHUB_TOKEN")
    assert client.token == "env_token"


def test_github_client_from_env_not_set(mocker: MockerFixture) -> None:
    mocker.patch.dict(os.environ, clear=True)  # Ensure it's not set
    with pytest.raises(
        ValueError, match='Environment variable "MISSING_TOKEN" is not set.'
    ):
        GithubClient.from_env(key="MISSING_TOKEN")


@pytest.mark.asyncio
async def test_get_repositories_empty(
    client: GithubClient, mocker: MockerFixture
) -> None:
    mocker.patch.object(client, "_make_request", AsyncMock(return_value=[]))
    repos = await client.get_repositories()
    assert repos == []


@pytest.mark.asyncio
async def test_get_repositories_none_response(
    client: GithubClient, mocker: MockerFixture
) -> None:
    # Simulate 204 or error leading to None
    mocker.patch.object(client, "_make_request", AsyncMock(return_value=None))
    repos = await client.get_repositories()
    # Should return empty list
    assert repos == []


@pytest.mark.asyncio
async def test_get_repositories_api_error(
    client: GithubClient, mocker: MockerFixture
) -> None:
    mocker.patch.object(
        client, "_make_request", AsyncMock(side_effect=GithubAPIError("API Error"))
    )
    with pytest.raises(GithubAPIError):
        await client.get_repositories()


@pytest.mark.asyncio
async def test_get_issues_success(client: GithubClient, mocker: MockerFixture) -> None:
    mock_data = [{"title": "issue1"}]
    mock_make_request = AsyncMock(return_value=mock_data)
    mocker.patch.object(client, "_make_request", mock_make_request)

    issues = await client.get_issues("owner", "repo")

    assert issues == mock_data
    mock_make_request.assert_called_once_with(
        "GET", "repos/owner/repo/issues", params={"state": "all", "per_page": 100}
    )


@pytest.mark.asyncio
async def test_get_teams_success(client: GithubClient, mocker: MockerFixture) -> None:
    mock_data = [{"name": "team-a"}]
    mock_make_request = AsyncMock(return_value=mock_data)
    mocker.patch.object(client, "_make_request", mock_make_request)

    teams = await client.get_teams("my-org")

    assert teams == mock_data
    mock_make_request.assert_called_once_with(
        "GET", "orgs/my-org/teams", params={"per_page": 100}
    )


@pytest.mark.asyncio
async def test_get_workflows_success(
    client: GithubClient, mocker: MockerFixture
) -> None:
    mock_response_data = {"total_count": 1, "workflows": [{"name": "ci.yml"}]}
    mock_make_request = AsyncMock(return_value=mock_response_data)
    mocker.patch.object(client, "_make_request", mock_make_request)

    workflows = await client.get_workflows("owner", "repo")

    assert workflows == [{"name": "ci.yml"}]
    mock_make_request.assert_called_once_with(
        "GET", "repos/owner/repo/actions/workflows", params={"per_page": 100}
    )


@pytest.mark.asyncio
async def test_get_workflows_no_workflows_key(
    client: GithubClient, mocker: MockerFixture
) -> None:
    # Missing "workflows" key
    mock_response_data = {"total_count": 0}
    mocker.patch.object(
        client, "_make_request", AsyncMock(return_value=mock_response_data)
    )
    workflows = await client.get_workflows("owner", "repo")
    assert workflows == []


@pytest.mark.asyncio
async def test_get_workflows_data_is_none(
    client: GithubClient, mocker: MockerFixture
) -> None:
    mocker.patch.object(client, "_make_request", AsyncMock(return_value=None))
    workflows = await client.get_workflows("owner", "repo")
    assert workflows == []
