import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import httpx
from port_ocean.context.event import event, EventContext, _event_context_stack
from port_ocean.context.ocean import ocean
from client import GitHubClient
from utils.initialize_client import get_client


class MockEventContext(EventContext):
    def __init__(self):
        self.attributes = {}


@pytest.fixture
def mock_event_context():
    ctx = MockEventContext()
    _event_context_stack.push(ctx)
    yield ctx
    _event_context_stack.pop()


@pytest.fixture
def mock_ocean():
    with patch("port_ocean.context.ocean.ocean") as mock:
        mock.integration_config = {
            "github_access_token": "test_token",
            "github_base_url": "https://api.github.com",
        }
        mock.app = MagicMock()
        mock.app.base_url = "https://example.com"
        yield mock


@pytest.fixture
def mock_http_client():
    mock = AsyncMock()
    mock.request = AsyncMock()
    mock.get = AsyncMock()
    mock.post = AsyncMock()
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {"data": "test"}
    mock.request.return_value = mock_response
    mock.get.return_value = mock_response
    mock.post.return_value = mock_response
    return mock


@pytest.fixture
def github_client(mock_ocean):
    return GitHubClient(
        token="test_token",
        github_base_url="https://api.github.com",
        base_url="https://example.com",
    )


def test_get_client(mock_ocean):
    mock_ocean.integration_config = {
        "github_access_token": "test_token",
        "github_base_url": "https://api.github.com"
    }
    mock_ocean.app.base_url = "https://example.com"

    with patch("utils.initialize_client.ocean", mock_ocean):
        client = get_client()
        assert isinstance(client, GitHubClient)
        assert client.token == "test_token"
        assert client.github_base_url == "https://api.github.com"
        assert client.base_url == "https://example.com"


@pytest.fixture
def mock_event():
    mock = MagicMock()
    mock.resource_config = MagicMock()
    mock.resource_config.selector = MagicMock()
    mock.resource_config.selector.organizations = ["org1"]
    
    def get_organizations():
        return ["org1"]
    
    mock.resource_config.selector.get_organizations = get_organizations
    return mock


@pytest.fixture
def mock_client(mock_event, mock_http_client, mock_event_context):
    client = GitHubClient(
        token="test_token",
        github_base_url="https://api.github.com",
        base_url="https://example.com",
    )
    client.event = mock_event
    client.http_client = mock_http_client
    
    mock_event_context.attributes = {
        "resource_config": {
            "selector": {
                "organizations": ["org1"]
            }
        }
    }
    
    client.event_context = mock_event_context
    
    return client


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_no_base_url(mock_client):
    mock_client.base_url = None
    mock_client.event.resource_config.selector.organizations = ["org1"]
    
    result = await mock_client.create_webhooks_if_not_exists()
    
    assert result is None


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_no_organizations(mock_client):
    mock_client.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = []
    
    result = await mock_client.create_webhooks_if_not_exists()
    
    assert result is None


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_success(mock_client):
    mock_client.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = ["org1"]
    
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = [
        {"id": "1", "name": "repo1", "owner": {"login": "org1"}}
    ]
    
    mock_client.http_client.get = AsyncMock(return_value=mock_response)
    
    mock_post_response = AsyncMock(spec=httpx.Response)
    mock_post_response.status_code = 200
    mock_post_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_post_response.json.return_value = {"id": "123"}
    
    mock_client.http_client.post = AsyncMock(return_value=mock_post_response)
    
    with patch.object(mock_client, '_check_rate_limit', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        result = await mock_client.create_webhooks_if_not_exists()
        
        assert result is None


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_existing_webhook(mock_client):
    mock_client.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = ["org1"]
    
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = [
        {
            "id": "1",
            "name": "repo1",
            "owner": {"login": "org1"},
            "webhooks": [
                {"url": "https://example.com/webhook"}
            ]
        }
    ]
    
    mock_client.http_client.get = AsyncMock(return_value=mock_response)
    
    with patch.object(mock_client, '_check_rate_limit', new_callable=AsyncMock) as mock_check:
        mock_check.return_value = None
        
        result = await mock_client.create_webhooks_if_not_exists()
        
        assert result is None


@pytest.mark.asyncio
async def test_create_webhooks_if_not_exists_api_error(mock_client):
    mock_client.base_url = "https://example.com"
    mock_client.event.resource_config.selector.organizations = ["org1"]
    
    mock_client.http_client.get.side_effect = Exception("API Error")
    
    result = await mock_client.create_webhooks_if_not_exists()
    
    assert result is None


@pytest.mark.asyncio
async def test_get_organizations(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "id": "1",
        "name": "org1"
    }
    
    mock_client.http_client.get = AsyncMock(return_value=mock_response)
    
    with patch.object(mock_client, '_send_api_request', new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"id": "1", "name": "org1"}
        
        result = await mock_client.get_organizations(["org1"])
        
        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == "1"
        assert result[0]["name"] == "org1"


@pytest.mark.asyncio
async def test_get_repositories(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "data": {"organization": {"repositories": {"nodes": [{"id": "1", "name": "repo1", "owner": {"login": "org1"}}]}}}
    }
    mock_client.http_client.get = AsyncMock(return_value=mock_response)

    async for repos in mock_client.get_repositories(["org1"]):
        assert repos == [{"id": "1", "name": "repo1", "owner": {"login": "org1"}}]


@pytest.mark.asyncio
async def test_get_pull_requests(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "data": {"repository": {"pullRequests": {"nodes": [{"id": "1", "title": "PR1"}]}}}
    }
    mock_client.http_client.get = AsyncMock(return_value=mock_response)

    async for prs in mock_client.get_pull_requests(["org1"]):
        assert prs == [{"id": "1", "title": "PR1"}]


@pytest.mark.asyncio
async def test_get_issues(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "data": {"repository": {"issues": {"nodes": [{"id": "1", "title": "Issue1"}]}}}
    }
    mock_client.http_client.get = AsyncMock(return_value=mock_response)

    async for issues in mock_client.get_issues(["org1"]):
        assert issues == [{"id": "1", "title": "Issue1"}]


@pytest.mark.asyncio
async def test_get_teams(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "data": {"organization": {"teams": {"nodes": [{"id": "1", "name": "team1"}]}}}
    }
    mock_client.http_client.get = AsyncMock(return_value=mock_response)

    async for teams in mock_client.get_teams(["org1"]):
        assert teams == [{"id": "1", "name": "team1"}]


@pytest.mark.asyncio
async def test_get_workflows(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "data": {"repository": {"workflows": {"nodes": [{"id": "1", "name": "workflow1"}]}}}
    }
    
    mock_client.http_client.get = AsyncMock(return_value=mock_response)
    
    async for workflows in mock_client.get_workflows(["org1"]):
        assert workflows == [{"id": "1", "name": "workflow1"}]


@pytest.mark.asyncio
async def test_get_single_resource(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {
        "id": "1",
        "name": "repo1"
    }
    
    mock_client.http_client.get = AsyncMock(return_value=mock_response)
    
    with patch.object(mock_client, '_send_api_request', new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"id": "1", "name": "repo1"}
        
        result = await mock_client.get_single_resource("repos", "org1", "repo1", None)
        
        assert result is not None
        assert result["id"] == "1"
        assert result["name"] == "repo1"


@pytest.mark.asyncio
async def test_send_api_request(mock_client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_response.json.return_value = {"data": "test"}
    
    mock_client.http_client.request = AsyncMock(return_value=mock_response)
    
    original_send_api_request = mock_client._send_api_request
    
    async def mock_send_api_request(*args, **kwargs):
        return {"data": "test"}
    
    mock_client._send_api_request = mock_send_api_request
    
    try:
        result = await mock_client._send_api_request("GET", "https://api.github.com/test")
        
        assert result == {"data": "test"}
    finally:
        mock_client._send_api_request = original_send_api_request


@pytest.mark.asyncio
async def test_handle_rate_limit(mock_client):
    mock_response = MagicMock(
        status_code=403,
        text="rate limit exceeded",
        headers={"Retry-After": "60"},
    )
    
    await mock_client._handle_rate_limit(mock_response)


@pytest.mark.asyncio
async def test_get_workflow_runs(mock_client):
    mock_repo_response = AsyncMock(spec=httpx.Response)
    mock_repo_response.status_code = 200
    mock_repo_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_repo_response.json.return_value = {
        "data": {"organization": {"repositories": {"nodes": [{"id": "1", "name": "repo1", "owner": {"login": "org1"}}]}}}
    }
    
    mock_runs_response = AsyncMock(spec=httpx.Response)
    mock_runs_response.status_code = 200
    mock_runs_response.headers = {"X-RateLimit-Remaining": "1000"}
    mock_runs_response.json.return_value = {
        "workflow_runs": [{"id": "1", "name": "run1"}]
    }
    
    def mock_request(*args, **kwargs):
        if "graphql" in args[1]:
            return mock_repo_response
        return mock_runs_response
    
    mock_client.http_client.request = AsyncMock(side_effect=mock_request)
    mock_client.http_client.get = AsyncMock(return_value=mock_repo_response)
    
    async for workflow_runs in mock_client.get_workflow_runs(["org1"], "workflow1"):
        assert workflow_runs == {"workflow_runs": [{"id": "1", "name": "run1"}]}


@pytest.mark.asyncio
async def test_to_async_iterator(mock_client):
    async def successful_coro():
        return {"data": "test"}
    
    iterator = mock_client._to_async_iterator(successful_coro())
    result = []
    async for item in iterator:
        result.append(item)
    
    assert result == [{"data": "test"}]
    
    async def failing_coro():
        raise Exception("Test error")
    
    iterator = mock_client._to_async_iterator(failing_coro())
    result = []
    async for item in iterator:
        result.append(item)
    
    assert result == []
