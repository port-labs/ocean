import time
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from github.client import GitHubClient, WEBHOOK_EVENTS
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

# ---------------------------------------------------------------------------
# Autouse fixture: Initialize PortOcean context.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def init_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "github_webhook_secret": "secret123",
            "client_timeout": 60,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

# ---------------------------------------------------------------------------
# Fixture for a dummy HTTP client (an AsyncMock) to replace the internal HTTP client.
# ---------------------------------------------------------------------------
@pytest.fixture
def dummy_client() -> MagicMock:
    dummy = MagicMock()
    dummy.request = AsyncMock()
    dummy.headers = {}
    return dummy

# ---------------------------------------------------------------------------
# Fixture for GitHubClient that patches the http_async_client (as imported in github.client).
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_github_client(dummy_client: MagicMock) -> GitHubClient:
    with patch("github.client.http_async_client", dummy_client):
        client = GitHubClient(token="test_token", org="test_org", repo="test_repo")
    return client

# ---------------------------------------------------------------------------
# Test functions for GitHubClient.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_client_initialization(mock_github_client: GitHubClient) -> None:
    headers = mock_github_client.client.headers
    assert headers.get("Authorization") == "Bearer test_token"
    assert headers.get("Accept") == "application/vnd.github+json"
    expected_url = "https://api.github.com/repos/test_org/test_repo/hooks"
    assert mock_github_client.webhook_url == expected_url

@pytest.mark.asyncio
async def test_request_success(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response_data = {"data": "value"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", url),
        json=response_data
    )
    mock_github_client.client.request.return_value = response

    result = await mock_github_client._request("GET", url)
    assert result.json() == response_data

    # Use built-in assertion instead of manually inspecting call_args.
    mock_github_client.client.request.assert_called_once_with("GET", url, params=None)

@pytest.mark.asyncio
async def test_request_failure(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response = httpx.Response(
        404,
        request=httpx.Request("GET", url)
    )
    mock_github_client.client.request.return_value = response

    with pytest.raises(httpx.HTTPStatusError):
        await mock_github_client._request("GET", url)

@pytest.mark.asyncio
async def test_request_rate_limit(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    current_time = int(time.time())
    reset_time = current_time + 2
    headers_rate_limit = {
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": str(reset_time)
    }
    response_rate_limit = httpx.Response(
        403,
        request=httpx.Request("GET", url),
        headers=headers_rate_limit
    )
    response_success = httpx.Response(
        200,
        request=httpx.Request("GET", url),
        json={"data": "value"}
    )
    # Simulate that the first call hits rate limiting and then it retries
    mock_github_client.client.request.side_effect = [response_rate_limit, response_success]

    # Override sleep to avoid delay.
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await mock_github_client._request("GET", url)
        assert result.json() == {"data": "value"}
        assert mock_sleep.await_count >= 1

@pytest.mark.asyncio
async def test_get(mock_github_client: GitHubClient) -> None:
    endpoint = "/test"
    url = f"{mock_github_client.base_url}{endpoint}"
    response = httpx.Response(
        200,
        request=httpx.Request("GET", url),
        json={"data": "value"}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response
        result = await mock_github_client.get(endpoint)
        mock_request.assert_called_once_with("GET", url, None)
        assert result.json() == {"data": "value"}

@pytest.mark.asyncio
async def test_get_paginated(mock_github_client: GitHubClient) -> None:
    endpoint = "/items"
    url = f"{mock_github_client.base_url}{endpoint}"
    first_response = httpx.Response(
        200,
        request=httpx.Request("GET", url),
        json=[{"id": 1}, {"id": 2}],
        headers={"Link": '<https://api.github.com/items?page=2>; rel="next"'}
    )
    second_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.github.com/items?page=2"),
        json=[],
        headers={}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [first_response, second_response]
        items = []
        async for item in mock_github_client.get_paginated(endpoint):
            items.append(item)
        assert items == [{"id": 1}, {"id": 2}]
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_create_webhooks_creates_new(mock_github_client: GitHubClient) -> None:
    app_host = "https://example.com"
    webhook_target = f"{app_host}/integration/webhook"

    response_get = httpx.Response(
        200,
        request=httpx.Request("GET", mock_github_client.webhook_url),
        json=[]
    )
    response_post = httpx.Response(
        201,
        request=httpx.Request("POST", mock_github_client.webhook_url),
        json={"id": "new_webhook"}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        # Simulate: first call returns an empty list; then POST succeeds.
        mock_request.side_effect = [response_get, response_post]
        await mock_github_client.create_webhooks(app_host)
        calls = mock_request.call_args_list
        assert len(calls) >= 2, "Expected at least 2 calls to _request (GET then POST)"

        # For the GET call:
        get_call = calls[0]
        method_get = get_call.kwargs.get("method", get_call.args[0] if get_call.args else None)
        url_get = get_call.kwargs.get("url", get_call.args[1] if len(get_call.args) > 1 else None)
        assert method_get == "GET"
        assert url_get == mock_github_client.webhook_url

        # For the POST call:
        post_call = calls[1]
        method_post = post_call.kwargs.get("method", post_call.args[0] if post_call.args else None)
        url_post = post_call.kwargs.get("url", post_call.args[1] if len(post_call.args) > 1 else None)
        assert method_post == "POST"
        assert url_post == mock_github_client.webhook_url

        post_params = post_call.kwargs["params"]
        assert post_params["config"]["url"] == webhook_target
        assert post_params["events"] == WEBHOOK_EVENTS


@pytest.mark.asyncio
async def test_create_webhooks_already_exists(mock_github_client: GitHubClient) -> None:
    app_host = "https://example.com"
    webhook_target = f"{app_host}/integration/webhook"
    existing_hook = {"config": {"url": webhook_target}}
    response_get = httpx.Response(
        200,
        request=httpx.Request("GET", mock_github_client.webhook_url),
        json=[existing_hook]
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_get  # response_get as defined earlier
        await mock_github_client.create_webhooks(app_host)
        # Instead of assert_called_once_with on positional arguments,
        # use keyword access:
        last_call = mock_request.call_args
        method = last_call.kwargs.get("method", last_call.args[0] if last_call.args else None)
        url_val = last_call.kwargs.get("url", last_call.args[1] if len(last_call.args) > 1 else None)
        assert method == "GET"
        assert url_val == mock_github_client.webhook_url


@pytest.mark.asyncio
async def test_fetch_workflow_run_success(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    workflow_data = {"id": run_id, "status": "completed"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}"),
        json=workflow_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_workflow_run(repo_owner, repo_name, run_id)
        mock_get.assert_called_once_with(endpoint)
        assert result == workflow_data

@pytest.mark.asyncio
async def test_fetch_workflow_run_failure(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    response = httpx.Response(
        404,
        request=httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_workflow_run(repo_owner, repo_name, run_id)
        mock_get.assert_called_once_with(endpoint)
        assert result is None
