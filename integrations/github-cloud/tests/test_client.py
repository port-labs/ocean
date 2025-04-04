import pytest
from unittest.mock import MagicMock, patch
from client import GitHubClient, get_client
from port_ocean.context.event import event


@pytest.fixture
def mock_ocean():
    with patch("client.ocean") as mock:
        mock.integration_config = {
            "github_access_token": "test_token",
            "github_base_url": "https://api.github.com",
        }
        mock.app.base_url = "http://localhost:8000"
        yield mock


@pytest.fixture
def mock_http_client():
    with patch("client.http_async_client") as mock:
        yield mock


@pytest.fixture
def github_client(mock_ocean):
    return GitHubClient(
        token="test_token",
        github_base_url="https://api.github.com",
        base_url="http://localhost:8000",
    )


def test_get_client(mock_ocean):
    client = get_client()
    assert isinstance(client, GitHubClient)
    assert client.token == "test_token"
    assert client.github_base_url == "https://api.github.com"
    assert client.base_url == "http://localhost:8000"


@pytest.fixture
def mock_event():
    with patch("github_cloud.client.event") as mock:
        mock.resource_config = MagicMock()
        mock.resource_config.selector.organizations = ["org1"]
        yield mock


@pytest.fixture
def mock_client(mock_event, mock_http_client):
    return get_client()


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_no_base_url(mock_client):
    mock_client.event.resource_config.base_url = None
    result = await mock_client.create_webhooks_if_not_exists()
    assert result is None


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_no_organizations(mock_client):
    mock_client.event.resource_config.selector.organizations = []
    result = await mock_client.create_webhooks_if_not_exists()
    assert result is None


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_success(mock_client):
    mock_client.event.resource_config.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = ["org1"]
    mock_client.http_client.get.return_value = {"data": {"organization": {"repositories": {"nodes": []}}}}
    mock_client.http_client.post.return_value = {"data": {"createWebhook": {"webhook": {"id": "123"}}}}

    result = await mock_client.create_webhooks_if_not_exists()
    assert result is not None
    mock_client.http_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_existing_webhook(mock_client):
    mock_client.event.resource_config.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = ["org1"]
    mock_client.http_client.get.return_value = {
        "data": {
            "organization": {
                "repositories": {
                    "nodes": [{
                        "webhooks": {
                            "nodes": [{
                                "url": "https://example.com/webhook"
                            }]
                        }
                    }]
                }
            }
        }
    }

    result = await mock_client.create_webhooks_if_not_exists()
    assert result is not None
    mock_client.http_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_api_error(mock_client):
    mock_client.event.resource_config.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = ["org1"]
    mock_client.http_client.get.side_effect = Exception("API Error")

    result = await mock_client.create_webhooks_if_not_exists()
    assert result is None


@pytest.mark.asyncio
async def test_get_organizations(mock_client):
    mock_client.http_client.get.return_value = {"data": {"viewer": {"organizations": {"nodes": [{"login": "org1"}]}}}}
    orgs = [org async for org in mock_client.get_organizations()]
    assert orgs == [{"login": "org1"}]


@pytest.mark.asyncio
async def test_get_repositories(mock_client):
    mock_client.http_client.get.return_value = {"data": {"organization": {"repositories": {"nodes": [{"name": "repo1"}]}}}}
    repos = [repo async for repo in mock_client.get_repositories("org1")]
    assert repos == [{"name": "repo1"}]


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client):
    mock_client.http_client.get.return_value = {"data": {"repository": {"pullRequests": {"nodes": [{"number": 1}]}}}}
    prs = [pr async for pr in mock_client.get_pull_requests("org1", "repo1")]
    assert prs == [{"number": 1}]


@pytest.mark.asyncio
async def test_get_issues(mock_client):
    mock_client.http_client.get.return_value = {"data": {"repository": {"issues": {"nodes": [{"number": 1}]}}}}
    issues = [issue async for issue in mock_client.get_issues("org1", "repo1")]
    assert issues == [{"number": 1}]


@pytest.mark.asyncio
async def test_get_teams(mock_client):
    mock_client.http_client.get.return_value = {"data": {"organization": {"teams": {"nodes": [{"slug": "team1"}]}}}}
    teams = [team async for team in mock_client.get_teams("org1")]
    assert teams == [{"slug": "team1"}]


@pytest.mark.asyncio
async def test_get_workflows(mock_client):
    mock_client.http_client.get.return_value = {"data": {"repository": {"workflows": {"nodes": [{"id": "123"}]}}}}
    workflows = [workflow async for workflow in mock_client.get_workflows("org1", "repo1")]
    assert workflows == [{"id": "123"}]


@pytest.mark.asyncio
async def test_get_single_resource(mock_client):
    mock_client.http_client.get.return_value = {"data": {"repository": {"pullRequest": {"number": 1}}}}
    result = await mock_client.get_single_resource("pull_requests", "1", "org1", "repo1")
    assert result == {"number": 1}


@pytest.mark.asyncio
async def test_send_api_request(mock_client):
    mock_client.http_client.get.return_value = {"data": {"test": "value"}}
    result = await mock_client._send_api_request("query", {"var": "value"})
    assert result == {"test": "value"}


@pytest.mark.asyncio
async def test_handle_rate_limit(mock_client):
    mock_client.http_client.get.return_value = {"data": {"rateLimit": {"remaining": 0, "resetAt": "2024-01-01T00:00:00Z"}}}
    with pytest.raises(Exception):
        await mock_client._handle_rate_limit({"data": {"rateLimit": {"remaining": 0, "resetAt": "2024-01-01T00:00:00Z"}}})
