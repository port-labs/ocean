import asyncio
import time
from typing import Any, Dict, AsyncGenerator, Optional, List

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

# Import our GitHub client (assumed to be in github/client.py)
from github.client import GitHubClient

from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

# -----------------------------------------------------------------------------
# Helper functions for async generators
# -----------------------------------------------------------------------------
def make_async_gen(pages: List[List[Dict[str, Any]]]) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Returns an async generator that yields each page from the pages list.
    Each page is expected to be a list of dictionaries.
    """
    async def _gen():
        for page in pages:
            yield page
    return _gen()

def make_async_error(error: Exception) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Returns an async generator that raises the given error immediately.
    """
    async def _gen():
        raise error
        yield  # never reached
    return _gen()

# -----------------------------------------------------------------------------
# Autouse fixture: Initialize PortOcean context
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Fixture for a dummy HTTP client (an AsyncMock) that will replace http_async_client.
# -----------------------------------------------------------------------------
@pytest.fixture
def dummy_client() -> MagicMock:
    dummy = MagicMock()
    dummy.request = AsyncMock()
    dummy.headers = {}
    return dummy

# -----------------------------------------------------------------------------
# Fixture for GitHubClient that patches the http_async_client used in github.client.
# -----------------------------------------------------------------------------
@pytest.fixture
def mock_github_client(dummy_client: MagicMock) -> GitHubClient:
    with patch("github.client.http_async_client", dummy_client):
        # New GitHubClient requires token and org.
        client = GitHubClient(token="test_token", org="test_org")
    return client

# ============================================================================
# Tests for GitHubClient methods using the new API structure.
# ============================================================================

@pytest.mark.asyncio
async def test_client_initialization(mock_github_client: GitHubClient) -> None:
    headers = mock_github_client.client.headers
    assert headers.get("Authorization") == "Bearer test_token"
    assert headers.get("Accept") == "application/vnd.github+json"
    # Check that the base URL is set properly.
    assert mock_github_client.base_url == "https://api.github.com"

@pytest.mark.asyncio
async def test_request_success(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response_data = {"data": "value"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", url),
        json=response_data,
    )
    mock_github_client.client.request.return_value = response

    # _send_api_request returns a tuple: (data_list, raw_response)
    data, resp = await mock_github_client._send_api_request("GET", url)
    # When the JSON is a dict, it is wrapped in a list.
    assert data == [response_data]
    assert resp.json() == response_data

    # Use keyword arguments to match the actual call signature.
    mock_github_client.client.request.assert_called_once_with(
        method="GET", url=url, params=None, json=None
    )

@pytest.mark.asyncio
async def test_request_failure(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response = httpx.Response(
        404,
        request=httpx.Request("GET", url)
    )
    mock_github_client.client.request.return_value = response

    with pytest.raises(httpx.HTTPStatusError):
        await mock_github_client._send_api_request("GET", url)

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
    mock_github_client.client.request.side_effect = [response_rate_limit, response_success]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        data, resp = await mock_github_client._send_api_request("GET", url)
        assert data == [{"data": "value"}]
        assert resp.json() == {"data": "value"}
        # Check that we awaited for rate limiting.
        assert mock_sleep.await_count >= 1

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
    with patch.object(mock_github_client, "_send_api_request", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = [
            ([{"id": 1}, {"id": 2}], first_response),
            ([], second_response)
        ]
        pages = []
        async for page in mock_github_client.get_paginated(endpoint):
            pages.extend(page)
        assert pages == [{"id": 1}, {"id": 2}]
        assert mock_send.call_count == 2

# ---------------------- Tests for fetch_resource and related methods ---------------------------
# We use fetch_resource to wrap various endpoints via the resource types.
# The patched get_paginated method is replaced using our helper functions.

@pytest.mark.asyncio
async def test_fetch_workflow_run_success(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    workflow_data = {"id": run_id, "status": "completed"}
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[workflow_data]])
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("workflow_run", owner=repo_owner, repo=repo_name, run_id=run_id)
        result = None
        async for item in gen:
            result = item
        assert result == workflow_data
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_workflow_run_failure(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    req = httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    err_resp = httpx.Response(404, request=req)
    error = httpx.HTTPStatusError("Not Found", request=req, response=err_resp)
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_error(error)
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("workflow_run", owner=repo_owner, repo=repo_name, run_id=run_id)
        items = [item async for item in gen]
        assert items == []
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_repositories(mock_github_client: GitHubClient) -> None:
    endpoint = f"/orgs/test_org/repos"
    pages = [[{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}], []]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        repos = []
        async for repo in mock_github_client.fetch_resource("org_repos", org="test_org"):
            repos.append(repo)
        assert repos == [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}]
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_pull_requests(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    endpoint = f"/repos/test_org/{repo_name}/pulls"
    pages = [
        [{"number": 101, "title": "PR 101"}, {"number": 102, "title": "PR 102"}],
        []
    ]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        pulls = []
        async for pr in mock_github_client.fetch_resource("pull_requests", owner="test_org", repo=repo_name):
            pulls.append(pr)
        assert pulls == [{"number": 101, "title": "PR 101"}, {"number": 102, "title": "PR 102"}]
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_issues(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    endpoint = f"/repos/test_org/{repo_name}/issues"
    pages = [
        [{"number": 201, "title": "Issue 201"}, {"number": 202, "title": "Issue 202"}],
        []
    ]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        issues = []
        async for issue in mock_github_client.fetch_resource("issues", owner="test_org", repo=repo_name):
            issues.append(issue)
        assert issues == [{"number": 201, "title": "Issue 201"}, {"number": 202, "title": "Issue 202"}]
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_teams(mock_github_client: GitHubClient) -> None:
    endpoint = f"/orgs/test_org/teams"
    pages = [
        [{"id": 301, "name": "Team A"}, {"id": 302, "name": "Team B"}],
        []
    ]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        teams = []
        async for team in mock_github_client.fetch_resource("teamsFull", org="test_org"):
            teams.append(team)
        assert teams == [{"id": 301, "name": "Team A"}, {"id": 302, "name": "Team B"}]
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_workflows(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    endpoint = f"/repos/test_org/{repo_name}/actions/workflows"
    workflows_data = {"workflows": [{"id": 401, "name": "Workflow 1"}, {"id": 402, "name": "Workflow 2"}]}
    # For a dict response, the client wraps it in a list.
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[workflows_data]])
    ) as mock_paginated:
        workflows = []
        async for wf in mock_github_client.fetch_resource("workflows", owner="test_org", repo=repo_name):
            workflows.append(wf)
        assert workflows == [workflows_data]
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_team_success(mock_github_client: GitHubClient) -> None:
    org = "test_org"
    team_slug = "team1"
    endpoint = f"/orgs/{org}/teams/{team_slug}"
    team_data = {"id": 501, "name": "Team One"}
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[team_data]])
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("teams", org=org, team_slug=team_slug)
        result = None
        async for item in gen:
            result = item
        assert result == team_data
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_team_failure(mock_github_client: GitHubClient) -> None:
    org = "test_org"
    team_slug = "team1"
    endpoint = f"/orgs/{org}/teams/{team_slug}"
    req = httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    err_resp = httpx.Response(404, request=req)
    error = httpx.HTTPStatusError("Not Found", request=req, response=err_resp)
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_error(error)
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("teams", org=org, team_slug=team_slug)
        items = [item async for item in gen]
        assert items == []
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_repository_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    endpoint = f"/repos/{owner}/{repo_name}"
    repo_data = {"id": 601, "name": repo_name}
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[repo_data]])
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("repository", owner=owner, repo=repo_name)
        result = None
        async for item in gen:
            result = item
        assert result == repo_data
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_repository_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    endpoint = f"/repos/{owner}/{repo_name}"
    req = httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    err_resp = httpx.Response(404, request=req)
    error = httpx.HTTPStatusError("Not Found", request=req, response=err_resp)
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_error(error)
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("repository", owner=owner, repo=repo_name)
        items = [item async for item in gen]
        assert items == []
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_commit_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    commit_sha = "abc123"
    endpoint = f"/repos/{owner}/{repo_name}/commits/{commit_sha}"
    commit_data = {"sha": commit_sha, "message": "Initial commit"}
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[commit_data]])
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("commit", owner=owner, repo=repo_name, commit_sha=commit_sha)
        result = None
        async for item in gen:
            result = item
        assert result == commit_data
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_commit_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    commit_sha = "abc123"
    endpoint = f"/repos/{owner}/{repo_name}/commits/{commit_sha}"
    req = httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    err_resp = httpx.Response(404, request=req)
    error = httpx.HTTPStatusError("Not Found", request=req, response=err_resp)
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_error(error)
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("commit", owner=owner, repo=repo_name, commit_sha=commit_sha)
        items = [item async for item in gen]
        assert items == []
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_pull_request_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    pull_number = 10
    endpoint = f"/repos/{owner}/{repo_name}/pulls/{pull_number}"
    pr_data = {"number": pull_number, "title": "Add feature"}
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[pr_data]])
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("pull_request", owner=owner, repo=repo_name, pull_number=pull_number)
        result = None
        async for item in gen:
            result = item
        assert result == pr_data
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_pull_request_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    pull_number = 10
    endpoint = f"/repos/{owner}/{repo_name}/pulls/{pull_number}"
    req = httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    err_resp = httpx.Response(404, request=req)
    error = httpx.HTTPStatusError("Not Found", request=req, response=err_resp)
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_error(error)
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("pull_request", owner=owner, repo=repo_name, pull_number=pull_number)
        items = [item async for item in gen]
        assert items == []
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_issue_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    issue_number = 20
    endpoint = f"/repos/{owner}/{repo_name}/issues/{issue_number}"
    issue_data = {"number": issue_number, "title": "Bug report"}
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen([[issue_data]])
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("issue", owner=owner, repo=repo_name, issue_number=issue_number)
        result = None
        async for item in gen:
            result = item
        assert result == issue_data
        mock_paginated.assert_called_once_with(endpoint)

@pytest.mark.asyncio
async def test_fetch_issue_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    issue_number = 20
    endpoint = f"/repos/{owner}/{repo_name}/issues/{issue_number}"
    req = httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}")
    err_resp = httpx.Response(404, request=req)
    error = httpx.HTTPStatusError("Not Found", request=req, response=err_resp)
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_error(error)
    ) as mock_paginated:
        gen = mock_github_client.fetch_resource("issue", owner=owner, repo=repo_name, issue_number=issue_number)
        items = [item async for item in gen]
        assert items == []
        mock_paginated.assert_called_once_with(endpoint)
