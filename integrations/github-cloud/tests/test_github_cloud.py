import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from client import GithubHandler
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from github_cloud.webhooks import create_webhook_for_repo, delete_webhook_for_repo, get_webhook_for_repo

MOCK_GITHUB_BASE_URL = "https://api.github.com"
MOCK_APP_HOST = "https://api.github.com"
MOCK_GITHUB_ACCESS_TOKEN = "github-access-token"
MOCK_GITHUB_OWNER = "github-owner"

@pytest.fixture(autouse=True)
def mock_ocean_and_event_context():
    """Mock the ocean and event contexts for all tests."""
    with patch("client.ocean") as mock_ocean, patch("port_ocean.context.event._event_context_stack") as mock_event_stack:
        # Mock the ocean context
        mock_ocean.integration_config = {
            "github_access_token": MOCK_GITHUB_ACCESS_TOKEN,
            "github_base_url": MOCK_GITHUB_BASE_URL,
            "app_host": MOCK_APP_HOST,
        }
        mock_ocean.integration_router = MagicMock()
        mock_ocean.port_client = MagicMock()

        # Mock the event context stack
        mock_event_context = MagicMock()
        mock_event_context.attributes = {}
        mock_event_stack.top = mock_event_context

        try:
            initialize_port_ocean_context(mock_ocean)
        except PortOceanContextAlreadyInitializedError:
            pass

        yield mock_ocean, mock_event_context


@pytest.mark.asyncio
async def test_get_repositories() -> None:
    """Test fetching repositories."""
    mock_response = [{"id": 1, "name": "crimmit", "owner": {"login": MOCK_GITHUB_OWNER}}]

    with patch("client.http_async_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json = AsyncMock(return_value=mock_response)

        handler = GithubHandler()
        repos = []
        async for repo in handler.get_repositories():
            repos.append(repo)

        assert len(repos) == 1
        assert repos[0]["name"] == "crimmit"
        assert repos[0]["owner"]["login"] == MOCK_GITHUB_OWNER
        mock_get.assert_called_once_with(
            f"{handler.base_url}/user/repos", headers=handler.headers
        )


@pytest.mark.asyncio
async def test_get_issues() -> None:
    """Test fetching issues for a repository."""
    mock_response = [{"id": 1, "title": "Test Issue"}]

    with patch("client.http_async_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json = AsyncMock(return_value=mock_response)

        handler = GithubHandler()
        issues = []
        async for issue in handler.get_issues(MOCK_GITHUB_OWNER, "crimmit"):
            issues.append(issue)

        assert len(issues) == 1
        assert issues[0]["title"] == "Test Issue"
        mock_get.assert_called_once_with(
            f"{handler.base_url}/repos/{MOCK_GITHUB_OWNER}/crimmit/issues", headers=handler.headers
        )


@pytest.mark.asyncio
async def test_get_pull_requests() -> None:
    """Test fetching pull requests for a repository."""
    mock_response = [{"id": 1, "title": "Test PR"}]

    with patch("client.http_async_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json = AsyncMock(return_value=mock_response)

        handler = GithubHandler()
        pull_requests = []
        async for pr in handler.get_pull_requests(MOCK_GITHUB_OWNER, "crimmit"):
            pull_requests.append(pr)

        assert len(pull_requests) == 1
        assert pull_requests[0]["title"] == "Test PR"
        mock_get.assert_called_once_with(
            f"{handler.base_url}/repos/{MOCK_GITHUB_OWNER}/crimmit/pulls", headers=handler.headers
        )


@pytest.mark.asyncio
async def test_get_organizations() -> None:
    """Test fetching organizations."""
    mock_response = [{"login": "kanmitcode"}]

    with patch("client.http_async_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json = AsyncMock(return_value=mock_response)

        handler = GithubHandler()
        orgs = []
        async for org in handler.get_organizations():
            orgs.append(org)

        assert len(orgs) == 1
        assert orgs[0]["login"] == "kanmitcode"
        mock_get.assert_called_once_with(
            f"{handler.base_url}/user/orgs", headers=handler.headers
        )


@pytest.mark.asyncio
async def test_get_workflows() -> None:
    """Test fetching workflows for a repository."""
    mock_response = [{"id": 1, "name": "Test Workflow"}]

    with patch("client.http_async_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json = AsyncMock(return_value=mock_response)

        handler = GithubHandler()
        workflows = []
        async for workflow in handler.get_workflows(MOCK_GITHUB_OWNER, "test-repo"):
            workflows.append(workflow)

        assert len(workflows) == 1
        assert workflows[0]["name"] == "Test Workflow"
        mock_get.assert_called_once_with(
            f"{handler.base_url}/repos/{MOCK_GITHUB_OWNER}/test-repo/actions/workflows", headers=handler.headers
        )
        
@pytest.mark.asyncio
async def test_create_webhook_for_repo() -> None:
    """Test creating a webhook for a repository."""
    mock_response = AsyncMock()
    mock_response.status_code = 201

    with patch("client.http_async_client.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        handler = GithubHandler()
        await create_webhook_for_repo(handler, MOCK_GITHUB_OWNER, "crimmit")

        mock_post.assert_called_once_with(
            f"{handler.base_url}/repos/{MOCK_GITHUB_OWNER}/crimmit/hooks",
            headers=handler.headers,
            json={
                "name": "web",
                "active": True,
                "events": ["push", "pull_request", "issues"],
                "config": {
                    "url": "https://api.github.com/integration/hook/github-cloud",  # Corrected URL
                    "content_type": "json",
                    "insecure_ssl": "0",
                },
            },
        )


@pytest.mark.asyncio
async def test_delete_webhook_for_repo() -> None:
    """Test deleting a webhook for a repository."""
    mock_response = AsyncMock()
    mock_response.status_code = 204

    with patch("client.http_async_client.delete", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = mock_response

        handler = GithubHandler()
        await delete_webhook_for_repo(handler, MOCK_GITHUB_OWNER, "test-repo", 12345)

        mock_delete.assert_called_once_with(
            f"{handler.base_url}/repos/{MOCK_GITHUB_OWNER}/test-repo/hooks/12345",
            headers=handler.headers,
        )


@pytest.mark.asyncio
async def test_get_webhook_for_repo() -> None:
    """Test checking if a webhook exists for a repository."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(
        return_value=[
            {
                "id": 12345,
                "config": {"url": "https://api.github.com/integration/hook/github-cloud"},
            }
        ]
    )

    with patch("client.http_async_client.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        handler = GithubHandler()
        webhook = await get_webhook_for_repo(handler, MOCK_GITHUB_OWNER, "test-repo")

        assert webhook is not None
        assert webhook["id"] == 12345
        mock_get.assert_called_once_with(
            f"{handler.base_url}/repos/{MOCK_GITHUB_OWNER}/test-repo/hooks",
            headers=handler.headers,
        )