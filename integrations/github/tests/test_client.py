from typing import Any, Dict, AsyncGenerator, Optional
import asyncio
import time
import os

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

# Import our GitHub client (assumed to be in github/client.py)
from github.client import GitHubClient


from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

# ---------------------------------------------------------------------------
# Autouse fixture: Initialize PortOcean context
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
# Fixture for a dummy HTTP client (an AsyncMock) that will replace http_async_client.
# ---------------------------------------------------------------------------
@pytest.fixture
def dummy_client() -> MagicMock:
    dummy = MagicMock()
    dummy.request = AsyncMock()
    dummy.headers = {}
    return dummy

# ---------------------------------------------------------------------------
# Fixture for GitHubClient that patches the http_async_client used in github.client.
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_github_client(dummy_client: MagicMock) -> GitHubClient:
    with patch("github.client.http_async_client", dummy_client):
        client = GitHubClient(token="test_token", org="test_org", repo="test_repo")
    return client

# ---------------------------------------------------------------------------
# Tests for GitHubClient methods.
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
    response = httpx.Response(200,
                              request=httpx.Request("GET", url),
                              json=response_data)
    mock_github_client.client.request.return_value = response

    result = await mock_github_client._request("GET", url)
    assert result.json() == response_data

    mock_github_client.client.request.assert_called_once_with("GET", url, params=None)

@pytest.mark.asyncio
async def test_request_failure(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response = httpx.Response(404,
                              request=httpx.Request("GET", url))
    mock_github_client.client.request.return_value = response

    with pytest.raises(httpx.HTTPStatusError):
        await mock_github_client._request("GET", url)

@pytest.mark.asyncio
async def test_request_rate_limit(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    current_time = int(time.time())
    reset_time = current_time + 2
    headers_rate_limit = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset_time)}
    response_rate_limit = httpx.Response(403,
                                         request=httpx.Request("GET", url),
                                         headers=headers_rate_limit)
    response_success = httpx.Response(200,
                                      request=httpx.Request("GET", url),
                                      json={"data": "value"})
    mock_github_client.client.request.side_effect = [response_rate_limit, response_success]

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await mock_github_client._request("GET", url)
        assert result.json() == {"data": "value"}
        assert mock_sleep.await_count >= 1

@pytest.mark.asyncio
async def test_get(mock_github_client: GitHubClient) -> None:
    endpoint = "/test"
    url = f"{mock_github_client.base_url}{endpoint}"
    response = httpx.Response(200,
                              request=httpx.Request("GET", url),
                              json={"data": "value"})
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response
        result = await mock_github_client.get(endpoint)
        assert mock_request.call_args.args[0] == "GET"
        assert mock_request.call_args.args[1] == url
        assert result.json() == {"data": "value"}

@pytest.mark.asyncio
async def test_get_paginated(mock_github_client: GitHubClient) -> None:
    endpoint = "/items"
    url = f"{mock_github_client.base_url}{endpoint}"
    first_response = httpx.Response(200,
                                    request=httpx.Request("GET", url),
                                    json=[{"id": 1}, {"id": 2}],
                                    headers={"Link": '<https://api.github.com/items?page=2>; rel="next"'})
    second_response = httpx.Response(200,
                                     request=httpx.Request("GET", "https://api.github.com/items?page=2"),
                                     json=[],
                                     headers={})
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [first_response, second_response]
        items = []
        async for item in mock_github_client.get_paginated(endpoint):
            items.append(item)
        assert items == [{"id": 1}, {"id": 2}]
        assert mock_request.call_count == 2


@pytest.mark.asyncio
async def test_create_webhooks_already_exists(mock_github_client: GitHubClient) -> None:
    app_host = "https://example.com"
    webhook_target = f"{app_host}/integration/webhook"
    existing_hook = {"config": {"url": webhook_target}}
    response_get = httpx.Response(200,
                                  request=httpx.Request("GET", mock_github_client.webhook_url),
                                  json=[existing_hook])
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_get
        await mock_github_client.create_webhooks(app_host)
        # Here we expect that only one GET call was made.
        mock_request.assert_called_once_with("GET", url=mock_github_client.webhook_url)

@pytest.mark.asyncio
async def test_fetch_workflow_run_success(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    workflow_data = {"id": run_id, "status": "completed"}
    response = httpx.Response(200,
                              request=httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}"),
                              json=workflow_data)
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_workflow_run(repo_owner, repo_name, run_id)
        assert mock_get.call_args.args[0] == endpoint
        assert result == workflow_data

@pytest.mark.asyncio
async def test_fetch_workflow_run_failure(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    response = httpx.Response(404,
                              request=httpx.Request("GET", f"{mock_github_client.base_url}{endpoint}"))
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_workflow_run(repo_owner, repo_name, run_id)
        assert mock_get.call_args.args[0] == endpoint
        assert result is None

# ---------------- Additional Tests for GitHubClient methods ----------------

# Test fetch_repositories: simulate a paginated response returning repository items.
@pytest.mark.asyncio
async def test_fetch_repositories(mock_github_client: GitHubClient) -> None:
    # Create two simulated pages of repositories.
    first_response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/orgs/test_org/repos"),
        json=[{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}],
        headers={"Link": '<https://api.github.com/orgs/test_org/repos?page=2>; rel="next"'}
    )
    second_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.github.com/orgs/test_org/repos?page=2"),
        json=[],
        headers={}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [first_response, second_response]
        repos = []
        async for repo in mock_github_client.fetch_repositories():
            repos.append(repo)
        assert repos == [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}]
        assert mock_request.call_count == 2

# Test fetch_pull_requests: similar pattern; pass a repo name.
@pytest.mark.asyncio
async def test_fetch_pull_requests(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    first_response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/test_org/{repo_name}/pulls"),
        json=[{"number": 101, "title": "PR 101"}, {"number": 102, "title": "PR 102"}],
        headers={"Link": '<https://api.github.com/repos/test_org/repo1/pulls?page=2>; rel="next"'}
    )
    second_response = httpx.Response(
        200,
        request=httpx.Request("GET", f"https://api.github.com/repos/test_org/{repo_name}/pulls?page=2"),
        json=[],
        headers={}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [first_response, second_response]
        pulls = []
        async for pr in mock_github_client.fetch_pull_requests(repo_name):
            pulls.append(pr)
        assert pulls == [{"number": 101, "title": "PR 101"}, {"number": 102, "title": "PR 102"}]
        assert mock_request.call_count == 2

# Test fetch_issues: simulate issues retrieval in a paginated fashion.
@pytest.mark.asyncio
async def test_fetch_issues(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    first_response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/test_org/{repo_name}/issues"),
        json=[{"number": 201, "title": "Issue 201"}, {"number": 202, "title": "Issue 202"}],
        headers={"Link": '<https://api.github.com/repos/test_org/repo1/issues?page=2>; rel="next"'}
    )
    second_response = httpx.Response(
        200,
        request=httpx.Request("GET", f"https://api.github.com/repos/test_org/{repo_name}/issues?page=2"),
        json=[],
        headers={}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [first_response, second_response]
        issues = []
        async for issue in mock_github_client.fetch_issues(repo_name):
            issues.append(issue)
        assert issues == [{"number": 201, "title": "Issue 201"}, {"number": 202, "title": "Issue 202"}]
        assert mock_request.call_count == 2

# Test fetch_teams: simulate paginated teams.
@pytest.mark.asyncio
async def test_fetch_teams(mock_github_client: GitHubClient) -> None:
    first_response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/orgs/test_org/teams"),
        json=[{"id": 301, "name": "Team A"}, {"id": 302, "name": "Team B"}],
        headers={"Link": '<https://api.github.com/orgs/test_org/teams?page=2>; rel="next"'}
    )
    second_response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.github.com/orgs/test_org/teams?page=2"),
        json=[],
        headers={}
    )
    with patch.object(mock_github_client, "_request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [first_response, second_response]
        teams = []
        async for team in mock_github_client.fetch_teams():
            teams.append(team)
        assert teams == [{"id": 301, "name": "Team A"}, {"id": 302, "name": "Team B"}]
        assert mock_request.call_count == 2

# Test fetch_workflows: simulate a GET call that returns a JSON object with a "workflows" key.
@pytest.mark.asyncio
async def test_fetch_workflows(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    workflows_data = {"workflows": [{"id": 401, "name": "Workflow 1"}, {"id": 402, "name": "Workflow 2"}]}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/test_org/{repo_name}/actions/workflows"),
        json=workflows_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        workflows = []
        async for workflow in mock_github_client.fetch_workflows(repo_name):
            workflows.append(workflow)
        assert workflows == [{"id": 401, "name": "Workflow 1"}, {"id": 402, "name": "Workflow 2"}]
        mock_get.assert_called_once_with(f"/repos/test_org/{repo_name}/actions/workflows")

# Test fetch_files: simulate a GET call returning a JSON list.
@pytest.mark.asyncio
async def test_fetch_files(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    files_data = [{"name": "file1.txt"}, {"name": "file2.txt"}]
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/test_org/{repo_name}/contents"),
        json=files_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        files = []
        async for f in mock_github_client.fetch_files(repo_name):
            files.append(f)
        assert files == files_data
        mock_get.assert_called_once_with(f"/repos/test_org/{repo_name}/contents")

# Test fetch_team: success and failure scenarios.
@pytest.mark.asyncio
async def test_fetch_team_success(mock_github_client: GitHubClient) -> None:
    org = "test_org"
    team_slug = "team1"
    team_data = {"id": 501, "name": "Team One"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/orgs/{org}/teams/{team_slug}"),
        json=team_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_team(org, team_slug)
        mock_get.assert_called_once_with(f"/orgs/{org}/teams/{team_slug}")
        assert result == team_data

@pytest.mark.asyncio
async def test_fetch_team_failure(mock_github_client: GitHubClient) -> None:
    org = "test_org"
    team_slug = "team1"
    response = httpx.Response(
        404,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/orgs/{org}/teams/{team_slug}")
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_team(org, team_slug)
        mock_get.assert_called_once_with(f"/orgs/{org}/teams/{team_slug}")
        assert result is None

# Test fetch_repository: success and failure.
@pytest.mark.asyncio
async def test_fetch_repository_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    repo_data = {"id": 601, "name": repo_name}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}"),
        json=repo_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_repository(owner, repo_name)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}")
        assert result == repo_data

@pytest.mark.asyncio
async def test_fetch_repository_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    response = httpx.Response(
        404,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}")
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_repository(owner, repo_name)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}")
        assert result is None

# Test fetch_commit: success and failure.
@pytest.mark.asyncio
async def test_fetch_commit_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    commit_sha = "abc123"
    commit_data = {"sha": commit_sha, "message": "Initial commit"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}/commits/{commit_sha}"),
        json=commit_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_commit(owner, repo_name, commit_sha)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}/commits/{commit_sha}")
        assert result == commit_data

@pytest.mark.asyncio
async def test_fetch_commit_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    commit_sha = "abc123"
    response = httpx.Response(
        404,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}/commits/{commit_sha}")
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_commit(owner, repo_name, commit_sha)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}/commits/{commit_sha}")
        assert result is None

# Test fetch_pull_request: success and failure.
@pytest.mark.asyncio
async def test_fetch_pull_request_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    pull_number = 10
    pr_data = {"number": pull_number, "title": "Add feature"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}/pulls/{pull_number}"),
        json=pr_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_pull_request(owner, repo_name, pull_number)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}/pulls/{pull_number}")
        assert result == pr_data

@pytest.mark.asyncio
async def test_fetch_pull_request_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    pull_number = 10
    response = httpx.Response(
        404,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}/pulls/{pull_number}")
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_pull_request(owner, repo_name, pull_number)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}/pulls/{pull_number}")
        assert result is None

# Test fetch_issue: success and failure.
@pytest.mark.asyncio
async def test_fetch_issue_success(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    issue_number = 20
    issue_data = {"number": issue_number, "title": "Bug report"}
    response = httpx.Response(
        200,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}/issues/{issue_number}"),
        json=issue_data
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_issue(owner, repo_name, issue_number)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}/issues/{issue_number}")
        assert result == issue_data

@pytest.mark.asyncio
async def test_fetch_issue_failure(mock_github_client: GitHubClient) -> None:
    owner = "owner1"
    repo_name = "repo1"
    issue_number = 20
    response = httpx.Response(
        404,
        request=httpx.Request("GET", f"{mock_github_client.base_url}/repos/{owner}/{repo_name}/issues/{issue_number}")
    )
    with patch.object(mock_github_client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = response
        result = await mock_github_client.fetch_issue(owner, repo_name, issue_number)
        mock_get.assert_called_once_with(f"/repos/{owner}/{repo_name}/issues/{issue_number}")
        assert result is None

