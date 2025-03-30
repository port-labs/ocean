import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import List, Dict, Any

class AsyncIterator:
    def __init__(self, items: List[Dict[str, Any]]):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return self.items.pop(0)
        except IndexError:
            raise StopAsyncIteration

@pytest.mark.asyncio
async def test_get_single_resource(mocked_github_client: MagicMock) -> None:
    mocked_github_client.get_single_resource.return_value = {"id": 1, "name": "test_issue"}
    result = await mocked_github_client.get_single_resource("issue", "test_repo/1")
    assert result == {"id": 1, "name": "test_issue"}
    mocked_github_client.get_single_resource.assert_awaited_once_with("issue", "test_repo/1")

@pytest.mark.asyncio
async def test_get_repositories(mocked_github_client: MagicMock) -> None:
    repos = [{"name": "repo1"}, {"name": "repo2"}]
    iterator = AsyncIterator(repos.copy())
    mocked_github_client.get_repositories.return_value = iterator
    result = []
    async for repo in await mocked_github_client.get_repositories():
        result.append(repo)
    assert result == repos
    mocked_github_client.get_repositories.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_issues(mocked_github_client: MagicMock) -> None:
    issues = [{"title": "issue1"}, {"title": "issue2"}]
    iterator = AsyncIterator(issues.copy())
    mocked_github_client.get_issues.return_value = iterator
    result = []
    async for issue in await mocked_github_client.get_issues("owner", "repo"):
        result.append(issue)
    assert result == issues
    mocked_github_client.get_issues.assert_awaited_once_with("owner", "repo")

@pytest.mark.asyncio
async def test_get_pull_requests(mocked_github_client: MagicMock) -> None:
    prs = [{"title": "pr1"}, {"title": "pr2"}]
    iterator = AsyncIterator(prs.copy())
    mocked_github_client.get_pull_requests.return_value = iterator
    result = []
    async for pr in await mocked_github_client.get_pull_requests("owner", "repo"):
        result.append(pr)
    assert result == prs
    mocked_github_client.get_pull_requests.assert_awaited_once_with("owner", "repo")

@pytest.mark.asyncio
async def test_get_teams(mocked_github_client: MagicMock) -> None:
    teams = [
        {
            "id": 1,
            "name": "team1",
            "slug": "team-1",
            "description": "Team 1 description",
            "privacy": "closed"
        },
        {
            "id": 2,
            "name": "team2",
            "slug": "team-2",
            "description": "Team 2 description",
            "privacy": "secret"
        }
    ]
    iterator = AsyncIterator(teams.copy())
    mocked_github_client.get_teams.return_value = iterator
    result = []
    async for team in await mocked_github_client.get_teams("test-org"):
        result.append(team)
    assert result == teams
    mocked_github_client.get_teams.assert_awaited_once_with("test-org")

@pytest.mark.asyncio
async def test_get_workflows(mocked_github_client: MagicMock) -> None:
    workflows = [
        {
            "id": 1,
            "name": "CI",
            "path": ".github/workflows/ci.yml",
            "state": "active",
            "created_at": "2024-03-01T00:00:00Z",
            "updated_at": "2024-03-01T12:00:00Z"
        },
        {
            "id": 2,
            "name": "CD",
            "path": ".github/workflows/cd.yml",
            "state": "active",
            "created_at": "2024-03-02T00:00:00Z",
            "updated_at": "2024-03-02T12:00:00Z"
        }
    ]
    iterator = AsyncIterator(workflows.copy())
    mocked_github_client.get_workflows.return_value = iterator
    result = []
    async for workflow in await mocked_github_client.get_workflows("owner", "repo"):
        result.append(workflow)
    assert result == workflows
    mocked_github_client.get_workflows.assert_awaited_once_with("owner", "repo")

