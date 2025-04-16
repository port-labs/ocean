import time
from typing import Any, Dict, AsyncGenerator, List
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from github.client import GitHubClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


def make_async_gen(
    pages: List[List[Dict[str, Any]]]
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    async def _gen() -> AsyncGenerator[List[Dict[str, Any]], None]:
        for page in pages:
            yield page

    return _gen()


def make_async_error(error: Exception) -> AsyncGenerator[List[Dict[str, Any]], None]:
    async def _gen() -> AsyncGenerator[List[Dict[str, Any]], None]:
        raise error
        yield

    return _gen()


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


@pytest.fixture
def dummy_client() -> MagicMock:
    dummy = MagicMock()
    dummy.request = AsyncMock()
    dummy.headers = {}
    return dummy


@pytest.fixture
def mock_github_client(dummy_client: MagicMock) -> GitHubClient:
    with patch("github.client.http_async_client", dummy_client):
        client = GitHubClient(token="test_token", org="test_org")
    return client


@pytest.mark.asyncio
async def test_client_initialization(mock_github_client: GitHubClient) -> None:
    headers = mock_github_client.client.headers
    assert headers.get("Authorization") == "Bearer test_token"
    assert headers.get("Accept") == "application/vnd.github+json"
    assert mock_github_client.base_url == "https://api.github.com"


@pytest.mark.asyncio
async def test_request_success(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response_data = {"data": "value"}
    response = httpx.Response(
        200, request=httpx.Request("GET", url), json=response_data
    )
    mock_github_client.client.request.return_value = response
    data, resp = await mock_github_client._send_api_request("GET", url)
    assert data == [response_data]
    assert resp.json() == response_data
    mock_github_client.client.request.assert_called_once_with(
        method="GET", url=url, params=None, json=None
    )


@pytest.mark.asyncio
async def test_request_failure(mock_github_client: GitHubClient) -> None:
    url = "http://example.com"
    response = httpx.Response(404, request=httpx.Request("GET", url))
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
        "X-RateLimit-Reset": str(reset_time),
    }
    response_rate_limit = httpx.Response(
        403, request=httpx.Request("GET", url), headers=headers_rate_limit
    )
    response_success = httpx.Response(
        200, request=httpx.Request("GET", url), json={"data": "value"}
    )
    mock_github_client.client.request.side_effect = [
        response_rate_limit,
        response_success,
    ]
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        data, resp = await mock_github_client._send_api_request("GET", url)
        assert data == [{"data": "value"}]
        assert resp.json() == {"data": "value"}
        assert mock_sleep.await_count >= 1


@pytest.mark.asyncio
async def test_get_paginated(mock_github_client: GitHubClient) -> None:
    endpoint = "/items"
    base_url = mock_github_client.base_url
    url1 = f"{base_url}{endpoint}"
    first_response = httpx.Response(
        200,
        request=httpx.Request("GET", url1),
        json=[{"id": 1}, {"id": 2}],
        headers={"Link": '<https://api.github.com/items?page=2>; rel="next"'},
    )
    second_url = "https://api.github.com/items?page=2"
    second_response = httpx.Response(
        200, request=httpx.Request("GET", second_url), json=[], headers={}
    )
    with patch.object(
        mock_github_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_send:
        mock_send.side_effect = [
            ([{"id": 1}, {"id": 2}], first_response),
            ([], second_response),
        ]
        pages = []
        async for page in mock_github_client.get_paginated(endpoint):
            pages.extend(page)
        assert pages == [{"id": 1}, {"id": 2}]
        calls = mock_send.call_args_list
        assert calls[0][0] == ("GET", url1)
        assert calls[0][1] == {"query_params": None}
        assert calls[1][0] == ("GET", second_url)
        assert calls[1][1] == {"query_params": None}


@pytest.mark.asyncio
async def test_fetch_workflow_run_success(mock_github_client: GitHubClient) -> None:
    repo_owner = "test_org"
    repo_name = "test_repo"
    run_id = "123"
    endpoint = f"/repos/{repo_owner}/{repo_name}/actions/runs/{run_id}"
    workflow_data = {"id": run_id, "status": "completed"}
    with patch.object(
        mock_github_client,
        "get_paginated",
        return_value=make_async_gen([[workflow_data]]),
    ) as mock_paginated:
        gen = mock_github_client.fetch_single_github_resource(
            "workflow_run", owner=repo_owner, repo=repo_name, run_id=run_id
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == [workflow_data]
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
        gen = mock_github_client.fetch_single_github_resource(
            "workflow_run", owner=repo_owner, repo=repo_name, run_id=run_id
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == []
        mock_paginated.assert_called_once_with(endpoint)


@pytest.mark.asyncio
async def test_fetch_repositories(mock_github_client: GitHubClient) -> None:
    endpoint = "/orgs/test_org/repos"
    pages = [[{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}], []]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        repos = []
        async for page in mock_github_client.get_organization_repos(params=None):
            repos.extend(page)
        assert repos == [{"id": 1, "name": "repo1"}, {"id": 2, "name": "repo2"}]
        mock_paginated.assert_called_once_with(endpoint)


@pytest.mark.asyncio
async def test_fetch_pull_requests(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    endpoint = f"/repos/test_org/{repo_name}/pulls"
    pages = [
        [{"number": 101, "title": "PR 101"}, {"number": 102, "title": "PR 102"}],
        [],
    ]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        pulls = []
        async for page in mock_github_client.get_pull_requests(
            owner="test_org", repo=repo_name, params=None
        ):
            pulls.extend(page)
        assert pulls == [
            {"number": 101, "title": "PR 101"},
            {"number": 102, "title": "PR 102"},
        ]
        mock_paginated.assert_called_once_with(endpoint)


@pytest.mark.asyncio
async def test_fetch_issues(mock_github_client: GitHubClient) -> None:
    repo_name = "repo1"
    endpoint = f"/repos/test_org/{repo_name}/issues"
    pages = [
        [{"number": 201, "title": "Issue 201"}, {"number": 202, "title": "Issue 202"}],
        [],
    ]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        issues = []
        async for page in mock_github_client.get_issues(
            owner="test_org", repo=repo_name, params=None
        ):
            issues.extend(page)
        assert issues == [
            {"number": 201, "title": "Issue 201"},
            {"number": 202, "title": "Issue 202"},
        ]
        mock_paginated.assert_called_once_with(endpoint)


@pytest.mark.asyncio
async def test_fetch_teams(mock_github_client: GitHubClient) -> None:
    endpoint = "/orgs/test_org/teams"
    pages = [[{"id": 301, "name": "Team A"}, {"id": 302, "name": "Team B"}], []]
    with patch.object(
        mock_github_client, "get_paginated", return_value=make_async_gen(pages)
    ) as mock_paginated:
        teams = []
        async for page in mock_github_client.get_teams(params=None):
            teams.extend(page)
        assert teams == [{"id": 301, "name": "Team A"}, {"id": 302, "name": "Team B"}]
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
        gen = mock_github_client.fetch_single_github_resource(
            "teams", org=org, team_slug=team_slug
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == [team_data]
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
        gen = mock_github_client.fetch_single_github_resource(
            "teams", org=org, team_slug=team_slug
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == []
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
        gen = mock_github_client.fetch_single_github_resource(
            "repository", owner=owner, repo=repo_name
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == [repo_data]
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
        gen = mock_github_client.fetch_single_github_resource(
            "repository", owner=owner, repo=repo_name
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == []
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
        gen = mock_github_client.fetch_single_github_resource(
            "pull_request", owner=owner, repo=repo_name, pull_number=pull_number
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == [pr_data]
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
        gen = mock_github_client.fetch_single_github_resource(
            "pull_request", owner=owner, repo=repo_name, pull_number=pull_number
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == []
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
        gen = mock_github_client.fetch_single_github_resource(
            "issue", owner=owner, repo=repo_name, issue_number=issue_number
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == [issue_data]
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
        gen = mock_github_client.fetch_single_github_resource(
            "issue", owner=owner, repo=repo_name, issue_number=issue_number
        )
        results = []
        async for page in gen:
            results.extend(page)
        assert results == []
        mock_paginated.assert_called_once_with(endpoint)
