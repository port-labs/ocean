import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
from github_cloud.clients.base_client import HTTPBaseClient
from github_cloud.clients.auth_client import AuthClient
from github_cloud.clients.client_factory import create_github_client
from github_cloud.clients.github_client import GitHubCloudClient
from port_ocean.context.ocean import PortOceanContext

# Test AuthClient
def test_auth_client_headers():
    token = "test_token"
    auth_client = AuthClient(token)
    headers = auth_client.get_headers()

    assert headers["Authorization"] == f"token {token}"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["Content-Type"] == "application/json"

# Test HTTPBaseClient
@pytest.fixture
def mock_http_client():
    return AsyncMock()

@pytest.fixture
def base_client(mock_http_client):
    return HTTPBaseClient("https://api.github.com", "test_token", client=mock_http_client)

@pytest.mark.asyncio
async def test_send_api_request_success(base_client, mock_http_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": "test"}
    mock_response.content = b'{"data": "test"}'
    mock_http_client.request.return_value = mock_response

    response = await base_client.send_api_request("GET", "/test")
    assert response == {"data": "test"}
    mock_http_client.request.assert_called_once()

@pytest.mark.asyncio
async def test_send_api_request_404(base_client, mock_http_client):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {}
    mock_http_client.request.return_value = mock_response

    response = await base_client.send_api_request("GET", "/test")
    assert response == {}

@pytest.mark.asyncio
async def test_send_api_request_rate_limit(base_client, mock_http_client):
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"}
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403 Rate limit exceeded",
        request=MagicMock(),
        response=mock_response
    )
    mock_http_client.request.return_value = mock_response

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_sleep.side_effect = ValueError("Test error")
        with pytest.raises(ValueError):
            await base_client.send_api_request("GET", "/test")

@pytest.mark.asyncio
async def test_get_page_links(base_client):
    mock_response = MagicMock()
    mock_response.headers = {
        "Link": '<https://api.github.com/page2>; rel="next", <https://api.github.com/page1>; rel="prev"'
    }

    links = await base_client.get_page_links(mock_response)
    assert links["next"] == "https://api.github.com/page2"
    assert links["prev"] == "https://api.github.com/page1"

# Test ClientFactory
@pytest.fixture(autouse=True)
def mock_port_ocean():
    mock_app = MagicMock()
    mock_app.config = MagicMock()
    mock_app.config.client_timeout = 30
    mock_app.config.integration = MagicMock()
    mock_app.config.integration.config = {}

    mock_ocean = MagicMock(spec=PortOceanContext)
    mock_ocean.app = mock_app
    mock_ocean.integration_config = {
        "github_host": "https://api.github.com",
        "github_token": "test_token"
    }
    mock_ocean._app = mock_app
    mock_ocean.app.config.integration.config = {}

    with patch("github_cloud.clients.client_factory.ocean", mock_ocean):
        yield mock_ocean

def test_create_github_client(mock_port_ocean):
    assert mock_port_ocean._app is not None
    assert mock_port_ocean.app.config.integration.config is not None

    client = create_github_client()
    assert isinstance(client, GitHubCloudClient)

    client2 = create_github_client()
    assert client is client2
