from unittest.mock import AsyncMock, MagicMock

import pytest

from integrations.github.integration.utils.auth import AuthClient
from integrations.github.integration.clients.github import IntegrationClient
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Initialize mock Ocean context for all tests"""
    try:
        mock_app = MagicMock()
        mock_app.config.integration.config = {
            "base_url": "https://api.github.com",
            "personal_access_token": "test-token",
            "user_agent": "test-user-agent",
        }
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.mark.asyncio
class TestIntegrationClient:
    @pytest.fixture
    def client(self) -> IntegrationClient:
        # config setup
        access_token = ocean.integration_config.get("personal_access_token", None)
        user_agent = ocean.integration_config.get("user_agent", None)
        auth_client = AuthClient(access_token=access_token, user_agent=user_agent)
        return IntegrationClient(auth_client)

    # repos
    async def test_get_repositories(self, client: IntegrationClient) -> None:
        # arrange
        expected_repos = [
            {
                "id": 988683681,
                "node_id": "R_kgDOOu4doQ",
                "name": "ocean",
                "full_name": "username/ocean",
                "html_url": "https://github.com/username/ocean",
            }
        ]

        async def mock_fetch_data(*args, **kwargs):
            yield expected_repos

        # Patch the internal fetch method
        client._fetch_data = mock_fetch_data

        # act
        repos = []
        async for repo_batch in client.get_repositories():
            repos.extend(repo_batch)

        # assert
        assert repos == expected_repos

    # teams
    async def test_get_teams(self, client: IntegrationClient) -> None:
        # arrange
        expected_teams = [
            {
                "name": "backend",
                "id": 13145446,
                "node_id": "T_kwDOCBupxM4AyJVm",
                "slug": "backend",
                "description": "",
                "privacy": "closed",
                "notification_setting": "notifications_enabled",
                "url": "https://api.github.com/organizations/136030660/team/13145446",
                "html_url": "https://github.com/orgs/some-org/teams/backend",
                "members_url": "https://api.github.com/organizations/136030660/team/13145446/members{/member}",
                "repositories_url": "https://api.github.com/organizations/136030660/team/13145446/repos",
                "permission": "pull",
                "created_at": "2025-05-28T23:58:19Z",
                "updated_at": "2025-05-28T23:58:19Z",
                "members_count": 1,
                "repos_count": 0,
            }
        ]

        async def mock_fetch_data(*args, **kwargs):
            yield expected_teams

        # Patch the internal fetch method
        client._fetch_data = mock_fetch_data

        # act
        teams = []
        async for team_batch in client.get_teams():
            teams.extend(team_batch)

        # assert
        assert teams == expected_teams

    # issues
    async def test_get_issues(self, client: IntegrationClient) -> None:
        # arrange
        expected_issues = [
            {
                "url": "https://api.github.com/repos/sample-username/jamal-farm/issues/15",
                "repository_url": "https://api.github.com/repos/sample-username/jamal-farm",
                "labels_url": "https://api.github.com/repos/sample-username/jamal-farm/issues/15/labels{/name}",
                "comments_url": "https://api.github.com/repos/sample-username/jamal-farm/issues/15/comments",
                "events_url": "https://api.github.com/repos/sample-username/jamal-farm/issues/15/events",
                "html_url": "https://github.com/sample-username/jamal-farm/pull/15",
                "id": 881811790,
                "node_id": "MDExOlB1bGxSZXF1ZXN0NjM1Mzg2NDQ5",
                "number": 15,
                "title": "Bump lodash from 4.17.15 to 4.17.21 in /server/functions",
            }
        ]

        async def mock_fetch_data(*args, **kwargs):
            yield expected_issues

        # Patch the internal fetch method
        client._fetch_data = mock_fetch_data

        # act
        issues = []
        async for repo_batch in client.get_repositories():
            tasks = [client.get_issues(repo.get("name")) for repo in repo_batch]
            async for task in stream_async_iterators_tasks(*tasks):
                issues.extend(task)

        # assert
        assert issues == expected_issues

    # pull requests
    async def test_get_pull_requests(self, client: IntegrationClient) -> None:
        # arrange
        expected_prs = [
            {
                "url": "https://api.github.com/repos/sample-username/ocean/pulls/4",
                "id": 2550739248,
                "node_id": "PR_kwDOOu4doc6YCTEw",
                "html_url": "https://github.com/sample-username/ocean/pull/4",
                "diff_url": "https://github.com/sample-username/ocean/pull/4.diff",
                "patch_url": "https://github.com/sample-username/ocean/pull/4.patch",
                "issue_url": "https://api.github.com/repos/sample-username/ocean/issues/4",
                "number": 4,
                "state": "open",
                "title": "Integrations/GitHub",
            }
        ]

        async def mock_fetch_data(*args, **kwargs):
            yield expected_prs

        # Patch the internal fetch method
        client._fetch_data = mock_fetch_data

        # act
        prs = []
        async for repo_batch in client.get_repositories():
            tasks = [client.get_pull_requests(repo.get("name")) for repo in repo_batch]
            async for task in stream_async_iterators_tasks(*tasks):
                prs.extend(task)

        # assert
        assert prs == expected_prs

    # workflows
    async def test_get_workflows(self, client: IntegrationClient) -> None:
        # arrange
        expected_prs = [
            {
                "id": 71631993,
                "node_id": "W_kwDOKQnkpM4ERQR5",
                "name": "Continuous Deployment",
                "path": ".github/workflows/cd.yml",
                "state": "active",
                "created_at": "2023-10-05T07:31:27.000+00:00",
                "updated_at": "2023-10-05T07:31:27.000+00:00",
                "url": "https://api.github.com/repos/sample-username/quantia-go/actions/workflows/71631993",
                "html_url": "https://github.com/sample-username/quantia-go/blob/dev/.github/workflows/cd.yml",
                "badge_url": "https://github.com/sample-username/quantia-go/workflows/Continuous%20Deployment/badge.svg",
            }
        ]

        async def mock_fetch_data(*args, **kwargs):
            yield expected_prs

        # Patch the internal fetch method
        client._fetch_data = mock_fetch_data

        # act
        prs = []
        async for repo_batch in client.get_repositories():
            tasks = [client.get_workflows(repo.get("name")) for repo in repo_batch]
            async for task in stream_async_iterators_tasks(*tasks):
                prs.extend(task)

        # assert
        assert prs == expected_prs
