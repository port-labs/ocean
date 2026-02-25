from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import BasicAuth, Request, Response
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira.client import PAGE_SIZE, WEBHOOK_EVENTS, OAUTH2_WEBHOOK_EVENTS, JiraClient
from jira.overrides import JiraIssueSelector


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.oauth_access_token_file_path = None
        mock_ocean_app.config.integration.config = {
            "jira_host": "https://getport.atlassian.net",
            "atlassian_user_email": "jira@atlassian.net",
            "atlassian_user_token": "asdf",
            "atlassian_organisation_id": "asdf",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.load_external_oauth_access_token = MagicMock(return_value=None)
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_jira_client() -> JiraClient:
    """Fixture to initialize JiraClient with mock parameters."""
    return JiraClient(
        jira_url="https://example.atlassian.net",
        jira_email="test@example.com",
        jira_token="test_token",
    )


@pytest.mark.asyncio
async def test_client_initialization(mock_jira_client: JiraClient) -> None:
    """Test the correct initialization of JiraClient."""
    assert mock_jira_client.jira_rest_url == "https://example.atlassian.net/rest"
    assert mock_jira_client.is_oauth_enabled() is False
    assert isinstance(mock_jira_client.jira_api_auth, BasicAuth)


@pytest.mark.asyncio
async def test_send_api_request_success(mock_jira_client: JiraClient) -> None:
    """Test successful API requests."""
    with patch.object(
        mock_jira_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            200, request=Request("GET", "http://example.com"), json={"key": "value"}
        )
        response = await mock_jira_client._send_api_request("GET", "http://example.com")
        assert response["key"] == "value"


@pytest.mark.asyncio
async def test_send_api_request_failure(mock_jira_client: JiraClient) -> None:
    """Test API request raising exceptions."""
    with patch.object(
        mock_jira_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            404, request=Request("GET", "http://example.com")
        )
        with pytest.raises(Exception):
            await mock_jira_client._send_api_request("GET", "http://example.com")


@pytest.mark.asyncio
async def test_get_single_project(mock_jira_client: JiraClient) -> None:
    """Test get_single_project method"""
    project_data: dict[str, Any] = {"key": "TEST", "name": "Test Project"}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = project_data
        result = await mock_jira_client.get_single_project("TEST")

        mock_request.assert_called_once_with(
            "GET", f"{mock_jira_client.api_url}/project/TEST"
        )
        assert result == project_data


@pytest.mark.asyncio
async def test_get_paginated_projects(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_projects method"""
    projects_data: dict[str, Any] = {
        "values": [{"key": "PROJ1"}, {"key": "PROJ2"}],
        "total": 2,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            projects_data,
            {"values": []},  # Empty response to end pagination
        ]

        projects: list[dict[str, Any]] = []
        async for project_batch in mock_jira_client.get_paginated_projects():
            projects.extend(project_batch)

        assert len(projects) == 2
        assert projects == projects_data["values"]
        mock_request.assert_called_with(
            "GET",
            f"{mock_jira_client.api_url}/project/search",
            params={"maxResults": PAGE_SIZE, "startAt": 0},
        )


@pytest.mark.asyncio
async def test_get_single_issue(mock_jira_client: JiraClient) -> None:
    """Test get_single_issue method"""
    issue_data: dict[str, Any] = {"key": "TEST-1", "fields": {"summary": "Test Issue"}}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = issue_data
        result = await mock_jira_client.get_single_issue("TEST-1")

        mock_request.assert_called_once_with(
            "GET", f"{mock_jira_client.api_url}/issue/TEST-1"
        )
        assert result == issue_data


@pytest.mark.asyncio
async def test_get_paginated_issues(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_issues with params including JQL filtering"""

    # Mock response data
    issues_data = {"issues": [{"key": "TEST-1"}, {"key": "TEST-2"}], "total": 2}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [issues_data, {"issues": []}]

        issues = []
        async for issue_batch in mock_jira_client.get_paginated_issues(
            params={"jql": "project = TEST"}
        ):
            issues.extend(issue_batch)

        assert len(issues) == 2
        assert issues == issues_data["issues"]

        # Verify params were passed correctly
        mock_request.assert_called_with(
            "GET",
            f"{mock_jira_client.api_url}/search/jql",
            params={"jql": "project = TEST"},
        )


@pytest.mark.asyncio
async def test_get_paginated_issues_with_jql_param(
    mock_jira_client: JiraClient,
) -> None:
    """Test get_paginated_issues with JQL parameter"""
    issues_data = {"issues": [{"key": "TEST-1"}, {"key": "TEST-2"}], "total": 2}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [issues_data, {"issues": []}]

        issues = []
        async for issue_batch in mock_jira_client.get_paginated_issues(
            params={"jql": "project = TEST"}
        ):
            issues.extend(issue_batch)

        assert len(issues) == 2


@pytest.mark.asyncio
async def test_get_paginated_issues_without_jql_param(
    mock_jira_client: JiraClient,
) -> None:
    """Test get_paginated_issues without JQL parameter - should use default JQL"""
    issues_data = {"issues": [{"key": "TEST-1"}, {"key": "TEST-2"}], "total": 2}
    default_jql = "(statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)"

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [issues_data, {"issues": []}]

        issues = []
        async for issue_batch in mock_jira_client.get_paginated_issues(
            params={"jql": default_jql}
        ):
            issues.extend(issue_batch)

        assert len(issues) == 2
        mock_request.assert_called_with(
            "GET",
            f"{mock_jira_client.api_url}/search/jql",
            params={"jql": default_jql},
        )


@pytest.mark.asyncio
async def test_get_paginated_issues_with_empty_jql(
    mock_jira_client: JiraClient,
) -> None:
    """Test get_paginated_issues with empty JQL - should use default JQL and /search/jql endpoint"""
    issues_data = {"issues": [{"key": "TEST-1"}, {"key": "TEST-2"}], "total": 2}
    custom_jql = "project = MYPROJECT ORDER BY updated DESC"

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [issues_data, {"issues": []}]

        issues = []
        async for issue_batch in mock_jira_client.get_paginated_issues(
            params={"jql": custom_jql}
        ):
            issues.extend(issue_batch)

        assert len(issues) == 2
        mock_request.assert_called_with(
            "GET",
            f"{mock_jira_client.api_url}/search/jql",
            params={"jql": custom_jql},
        )


@pytest.mark.asyncio
async def test_get_single_user(mock_jira_client: JiraClient) -> None:
    """Test get_single_user method"""
    user_data: dict[str, Any] = {
        "accountId": "test123",
        "emailAddress": "test@example.com",
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = user_data
        result = await mock_jira_client.get_single_user("test123")

        mock_request.assert_called_once_with(
            "GET", f"{mock_jira_client.api_url}/user", params={"accountId": "test123"}
        )
        assert result == user_data


@pytest.mark.asyncio
async def test_get_paginated_users(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_users method"""
    users_data: list[dict[str, Any]] = [{"accountId": "user1"}, {"accountId": "user2"}]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [users_data, []]  # Empty response to end pagination

        users: list[dict[str, Any]] = []
        async for user_batch in mock_jira_client.get_paginated_users():
            users.extend(user_batch)

        assert len(users) == 2
        assert users == users_data


@pytest.mark.asyncio
async def test_get_paginated_teams(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_teams method"""
    # Mock data
    teams_data: dict[str, Any] = {
        "entities": [
            {"teamId": "team1", "name": "Team 1"},
            {"teamId": "team2", "name": "Team 2"},
        ],
        "cursor": None,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            teams_data,
            {"entities": []},  # Empty response to end pagination
        ]

        teams: list[dict[str, Any]] = []
        async for team_batch in mock_jira_client.get_paginated_teams("test_org_id"):
            teams.extend(team_batch)

        assert len(teams) == 2
        assert teams == teams_data["entities"]


@pytest.mark.asyncio
async def test_get_paginated_teams_multiple_pages(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_teams method with multiple pages"""
    # First page response with cursor
    page1_response = {
        "entities": [
            {"teamId": "team1", "name": "Team 1"},
            {"teamId": "team2", "name": "Team 2"},
        ],
        "cursor": "next_page_cursor",
    }

    # Second page response without cursor (end of pagination)
    page2_response = {
        "entities": [
            {"teamId": "team3", "name": "Team 3"},
        ],
        "cursor": None,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1_response, page2_response]

        teams: list[dict[str, Any]] = []
        async for team_batch in mock_jira_client.get_paginated_teams("test_org_id"):
            teams.extend(team_batch)

        assert len(teams) == 3
        assert teams[0]["teamId"] == "team1"
        assert teams[1]["teamId"] == "team2"
        assert teams[2]["teamId"] == "team3"

        # Verify the second call includes the cursor
        second_call = mock_request.call_args_list[1]
        assert second_call[1]["params"]["cursor"] == "next_page_cursor"


@pytest.mark.asyncio
async def test_get_paginated_team_members(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_team_members with example API response format"""
    page1_response = {
        "results": [{"accountId": "user1"}, {"accountId": "user2"}],
        "pageInfo": {"endCursor": "cursor1", "hasNextPage": True},
    }
    page2_response = {
        "results": [{"accountId": "user3"}],
        "pageInfo": {"endCursor": "cursor2", "hasNextPage": False},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1_response, page2_response]

        members: list[dict[str, Any]] = []
        async for member_batch in mock_jira_client.get_paginated_team_members(
            "team1", "test-org"
        ):
            members.extend(member_batch)

        assert len(members) == 3


@pytest.mark.asyncio
async def test_create_events_webhook(mock_jira_client: JiraClient) -> None:
    """Test create_events_webhook method"""
    app_host = "https://example.com"
    webhook_url = f"{app_host}/integration/webhook"

    # Test when webhook doesn't exist
    with (
        patch.object(
            mock_jira_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            mock_jira_client, "has_webhook_permission", new_callable=AsyncMock
        ) as mock_permission,
    ):
        mock_permission.return_value = True
        mock_request.side_effect = [
            [],  # No existing webhooks
            {"id": "new_webhook"},  # Creation response
        ]

        await mock_jira_client.create_webhooks(app_host)

        # Verify webhook creation call
        create_call = mock_request.call_args_list[1]
        assert create_call[0][0] == "POST"
        assert create_call[0][1] == mock_jira_client.webhooks_url
        assert create_call[1]["json"]["url"] == webhook_url
        assert create_call[1]["json"]["events"] == WEBHOOK_EVENTS

    # Test when webhook already exists
    with (
        patch.object(
            mock_jira_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            mock_jira_client, "has_webhook_permission", new_callable=AsyncMock
        ) as mock_permission,
    ):
        mock_permission.return_value = True
        mock_request.return_value = [{"url": webhook_url}]

        await mock_jira_client.create_webhooks(app_host)
        mock_request.assert_called_once()  # Only checks for existence


@pytest.mark.asyncio
async def test_create_webhooks_no_permission(mock_jira_client: JiraClient) -> None:
    """Test create_webhooks when user lacks ADMINISTER permission."""
    app_host = "https://example.com"

    with (
        patch.object(
            mock_jira_client, "has_webhook_permission", new_callable=AsyncMock
        ) as mock_permission,
        patch.object(
            mock_jira_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_permission.return_value = False

        await mock_jira_client.create_webhooks(app_host)

        mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_create_events_webhook_oauth(mock_jira_client: JiraClient) -> None:
    """Test _create_events_webhook_oauth method"""
    app_host = "https://example.com"
    webhook_url = f"{app_host}/integration/webhook"

    # Mock the OAuth token to enable OAuth mode
    with (
        patch.object(mock_jira_client, "is_oauth_enabled", return_value=True),
        patch.object(
            mock_jira_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request,
        patch.object(
            mock_jira_client, "has_webhook_permission", new_callable=AsyncMock
        ) as mock_permission,
    ):
        mock_permission.return_value = True
        mock_request.side_effect = [
            {"values": []},  # No existing webhooks
            {"id": "new_webhook"},  # Creation response
        ]

        await mock_jira_client.create_webhooks(app_host)

        # Verify webhook creation call
        create_call = mock_request.call_args_list[1]
        assert create_call[0][0] == "POST"
        assert create_call[0][1] == mock_jira_client.webhooks_url
        assert create_call[1]["json"]["url"] == webhook_url
        assert create_call[1]["json"]["webhooks"][0]["events"] == OAUTH2_WEBHOOK_EVENTS
        assert "jqlFilter" in create_call[1]["json"]["webhooks"][0]

    # Test when webhook already exists
    with (
        patch.object(mock_jira_client, "is_oauth_enabled", return_value=True),
        patch.object(
            mock_jira_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request,
    ):
        mock_request.return_value = {"values": [{"url": webhook_url}]}

        await mock_jira_client.create_webhooks(app_host)
        mock_request.assert_called_once()  # Only checks for existence


@pytest.mark.asyncio
async def test_get_reconciled_issues(mock_jira_client: JiraClient) -> None:
    """Test get_reconciled_issues uses POST with correct body shape."""
    issues_data = {
        "issues": [{"key": "TEST-1", "id": "10001", "fields": {"summary": "Test"}}]
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = issues_data

        result = await mock_jira_client.get_reconciled_issues(
            jql="project = TEST AND key = TEST-1",
            issue_ids=[10001],
            fields="*all",
        )

        mock_request.assert_called_once_with(
            "POST",
            f"{mock_jira_client.api_url}/search/jql",
            json={
                "jql": "project = TEST AND key = TEST-1",
                "fields": ["*all"],
                "reconcileIssues": [10001],
                "maxResults": 1,
            },
        )
        assert len(result) == 1
        assert result[0]["key"] == "TEST-1"


@pytest.mark.asyncio
async def test_get_reconciled_issues_empty_response(
    mock_jira_client: JiraClient,
) -> None:
    """Test get_reconciled_issues returns empty list when no issues found."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"issues": []}

        result = await mock_jira_client.get_reconciled_issues(
            jql="key = NONEXISTENT-1",
            issue_ids=[99999],
        )

        assert result == []


@pytest.mark.asyncio
async def test_enrich_projects_with_releases(mock_jira_client: JiraClient) -> None:
    """Test enrich_projects_with_releases attaches __releases to each project."""
    projects: list[dict[str, Any]] = [{"key": "PROJ1"}, {"key": "PROJ2"}]

    async def mock_api_request(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        if "PROJ1" in url:
            return {
                "values": [{"id": 1001, "name": "v1.0"}, {"id": 1002, "name": "v1.1"}],
                "total": 2,
            }
        return {"values": [{"id": 2001, "name": "v2.0"}], "total": 1}

    with patch.object(
        mock_jira_client, "_send_api_request", side_effect=mock_api_request
    ):
        result = await mock_jira_client.enrich_projects_with_releases(projects)

    assert len(result) == 2
    proj1 = next(p for p in result if p["key"] == "PROJ1")
    proj2 = next(p for p in result if p["key"] == "PROJ2")
    assert len(proj1["__releases"]) == 2
    assert all(r["__projectKey"] == "PROJ1" for r in proj1["__releases"])
    assert len(proj2["__releases"]) == 1
    assert all(r["__projectKey"] == "PROJ2" for r in proj2["__releases"])


@pytest.mark.asyncio
async def test_enrich_projects_with_releases_empty(
    mock_jira_client: JiraClient,
) -> None:
    """Test enrich_projects_with_releases attaches an empty list for projects with no releases."""
    projects: list[dict[str, Any]] = [{"key": "EMPTY"}]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"values": [], "total": 0}
        result = await mock_jira_client.enrich_projects_with_releases(projects)

    assert result[0]["__releases"] == []


@pytest.mark.asyncio
async def test_enrich_projects_with_releases_pagination(
    mock_jira_client: JiraClient,
) -> None:
    """Test enrich_projects_with_releases collects releases across multiple pages."""
    projects: list[dict[str, Any]] = [{"key": "BIG"}]
    remainder = 10
    total = PAGE_SIZE + remainder
    page1 = {
        "values": [{"id": i, "name": f"v{i}"} for i in range(PAGE_SIZE)],
        "total": total,
    }
    page2 = {
        "values": [{"id": i, "name": f"v{i}"} for i in range(PAGE_SIZE, total)],
        "total": total,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page1, page2]
        result = await mock_jira_client.enrich_projects_with_releases(projects)

    assert len(result[0]["__releases"]) == total
    assert all(r["__projectKey"] == "BIG" for r in result[0]["__releases"])


@pytest.mark.asyncio
async def test_get_project_with_releases(mock_jira_client: JiraClient) -> None:
    """Test get_project_with_releases fetches a project and enriches it with __releases."""
    project_data: dict[str, Any] = {"id": 100, "key": "PROJ1", "name": "Project 1"}
    versions_response: dict[str, Any] = {
        "values": [{"id": 1001, "name": "v1.0"}],
        "total": 1,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [project_data, versions_response]
        result = await mock_jira_client.get_project_with_releases("PROJ1")

    assert result is not None
    assert result["key"] == "PROJ1"
    assert len(result["__releases"]) == 1
    assert result["__releases"][0]["__projectKey"] == "PROJ1"


def test_jira_issue_selector_default_jql() -> None:
    """Test that JiraIssueSelector uses the correct default JQL when not provided"""
    selector = JiraIssueSelector(query="true")

    expected_default_jql = (
        "(statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)"
    )
    assert (
        selector.jql == expected_default_jql
    ), f"Expected default JQL to be '{expected_default_jql}', but got '{selector.jql}'"

    assert (
        selector.fields == "*all"
    ), f"Expected default fields to be '*all', but got '{selector.fields}'"
