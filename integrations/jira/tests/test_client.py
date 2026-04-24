from typing import Any
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import BasicAuth, Request, Response
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira.client import (
    PAGE_SIZE,
    WEBHOOK_EVENTS,
    OAUTH2_WEBHOOK_EVENTS,
    BearerAuth,
    JiraClient,
)
from jira.overrides import JiraIssueSelector


MOCK_BOARD_API_RESPONSE = {
    "id": 1,
    "name": "PORT board",
    "type": "scrum",
    "self": "https://example.atlassian.net/rest/agile/1.0/board/1",
    "location": {
        "projectId": 10000,
        "projectKey": "PORT",
        "projectName": "Port Example Project",
        "projectTypeKey": "software",
        "displayName": "Port (PORT)",
    },
    "isPrivate": False,
}

MOCK_BOARD_WITH_ADMINS = {
    "id": 1,
    "name": "PORT board",
    "type": "scrum",
    "self": "https://exampleorg.atlassian.net/rest/agile/1.0/board/1",
    "location": {
        "projectId": 10000,
        "projectKey": "PORT",
        "projectName": "Port",
        "projectTypeKey": "software",
        "displayName": "Port (PORT)",
    },
    "isPrivate": False,
    "admins": {
        "users": [
            {"accountId": "abc123", "displayName": "Alice", "active": True},
            {"accountId": "def456", "displayName": "Bob", "active": True},
        ],
        "groups": [
            {"name": "jira-admins", "self": "https://..."},
            {"name": "platform-team", "self": "https://..."},
        ],
    },
}

MOCK_BOARD_WITH_NULL_ACCOUNT_IDS = {
    **MOCK_BOARD_WITH_ADMINS,
    "admins": {
        "users": [
            {"accountId": None, "displayName": "Ghost User", "active": False},
            {"accountId": "abc123", "displayName": "Alice", "active": True},
        ],
        "groups": [
            {"name": None, "self": "https://..."},
            {"name": "jira-admins", "self": "https://..."},
        ],
    },
}

MOCK_BOARD_WITHOUT_ADMINS = {
    "id": 2,
    "name": "DEMO board",
    "type": "simple",
    "self": "https://exampleorg.atlassian.net/rest/agile/1.0/board/2",
    "location": {
        "projectId": 10004,
        "projectKey": "DEMO",
        "projectName": "Demo",
        "projectTypeKey": "software",
        "displayName": "Demo (DEMO)",
    },
    "isPrivate": False,
    # admins field absent entirely
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config = MagicMock()
        mock_ocean_app.config.oauth_access_token_file_path = None
        mock_ocean_app.config.integration.config = {
            "jira_host": "https://exampleorg.atlassian.net",
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


def test_refresh_request_auth_creds_updates_global_auth(
    mock_jira_client: JiraClient,
) -> None:
    """Token refresh updates request header and default client auth for next requests."""
    request = Request("GET", "https://example.atlassian.net/rest/api/3/myself")
    refreshed_auth = BearerAuth("newly_refreshed_token")

    with patch.object(mock_jira_client, "_get_bearer", return_value=refreshed_auth):
        refreshed_request = mock_jira_client.refresh_request_auth_creds(request)

    assert refreshed_request.headers["Authorization"] == "Bearer newly_refreshed_token"
    assert mock_jira_client.jira_api_auth is refreshed_auth
    assert mock_jira_client.client.auth is refreshed_auth


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
            "POST",
            f"{mock_jira_client.api_url}/search/jql",
            json={"jql": "project = TEST", "maxResults": PAGE_SIZE},
            retryable=True,
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
            "POST",
            f"{mock_jira_client.api_url}/search/jql",
            json={"jql": default_jql, "maxResults": PAGE_SIZE},
            retryable=True,
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
            "POST",
            f"{mock_jira_client.api_url}/search/jql",
            json={"jql": custom_jql, "maxResults": PAGE_SIZE},
            retryable=True,
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
async def test_get_paginated_issues_with_reconcile(
    mock_jira_client: JiraClient,
) -> None:
    """Test get_paginated_issues with reconcileIssues uses correct POST body."""
    issues_data = {
        "issues": [{"key": "TEST-1", "id": "10001", "fields": {"summary": "Test"}}]
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = issues_data

        issues = []
        async for batch in mock_jira_client.get_paginated_issues(
            params={
                "jql": "project = TEST AND key = TEST-1",
                "fields": "*all",
                "reconcileIssues": [10001],
            }
        ):
            issues.extend(batch)

        mock_request.assert_called_once_with(
            "POST",
            f"{mock_jira_client.api_url}/search/jql",
            json={
                "jql": "project = TEST AND key = TEST-1",
                "fields": ["*all"],
                "reconcileIssues": [10001],
                "maxResults": 1,
            },
            retryable=True,
        )
        assert len(issues) == 1
        assert issues[0]["key"] == "TEST-1"


@pytest.mark.asyncio
async def test_get_paginated_issues_with_reconcile_empty_response(
    mock_jira_client: JiraClient,
) -> None:
    """Test get_paginated_issues with reconcileIssues returns empty when no issues found."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"issues": []}

        issues = []
        async for batch in mock_jira_client.get_paginated_issues(
            params={"jql": "key = NONEXISTENT-1", "reconcileIssues": [99999]}
        ):
            issues.extend(batch)

        assert issues == []


def test_validate_existing_webhook_warns_on_misconfiguration() -> None:
    """Test that all warnings fire for a misconfigured webhook."""
    webhook = {
        "name": "test-webhook",
        "filters": {"issue-related-events-section": "project = PROJ1"},
        "events": ["jira:issue_created"],
        "enabled": False,
    }
    with patch("jira.client.logger") as mock_logger:
        JiraClient._validate_existing_webhook(webhook, WEBHOOK_EVENTS, is_oauth=False)

        mock_logger.warning.assert_any_call(
            "Existing webhook has a JQL filter configured on Jira's side, "
            "which may prevent some events from being sent. JQL filter: project = PROJ1"
        )
        event_warning_calls = [
            str(call)
            for call in mock_logger.warning.call_args_list
            if "Existing webhook events do not match expected events" in str(call)
        ]
        assert len(event_warning_calls) == 1
        mock_logger.warning.assert_any_call(
            "Existing webhook is disabled and will not fire any events"
        )


def test_validate_existing_webhook_no_warnings_when_healthy() -> None:
    """Test that no warnings fire for a correctly configured webhook."""
    webhook = {
        "name": "test-webhook",
        "filters": {},
        "events": WEBHOOK_EVENTS,
        "enabled": True,
    }
    with patch("jira.client.logger") as mock_logger:
        JiraClient._validate_existing_webhook(webhook, WEBHOOK_EVENTS, is_oauth=False)

        mock_logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_get_paginated_versions(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_versions iterates over projects and yields enriched version batches."""

    versions_response: dict[str, Any] = {
        "values": [
            {"id": 1001, "name": "v1.0"},
            {"id": 1002, "name": "v1.1"},
        ],
        "total": 2,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            versions_response,
        ]

        all_versions: list[dict[str, Any]] = []
        async for batch in mock_jira_client.get_paginated_versions(project_key="PROJ1"):
            all_versions.extend(batch)

        mock_request.assert_called_once_with(
            "GET",
            f"{mock_jira_client.api_url}/project/PROJ1/version",
            params={"maxResults": PAGE_SIZE, "startAt": 0},
        )
        assert len(all_versions) == 2
        assert all_versions == versions_response["values"]
        assert all_versions[0]["__projectKey"] == "PROJ1"
        assert all_versions[1]["__projectKey"] == "PROJ1"


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


@pytest.mark.asyncio
async def test_jql_search_post_request_is_marked_retryable(
    mock_jira_client: JiraClient,
) -> None:
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {"issues": []}

        async for _ in mock_jira_client.get_paginated_issues(
            params={"jql": "project = TEST"}
        ):
            pass

        mock_request.assert_called_once_with(
            "POST",
            f"{mock_jira_client.api_url}/search/jql",
            json={"jql": "project = TEST", "maxResults": PAGE_SIZE},
            retryable=True,
        )


@pytest.mark.asyncio
async def test_agile_paginator_stops_when_is_last_true(
    mock_jira_client: JiraClient,
) -> None:
    """Paginator must stop when isLast is True even if items were returned."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
            "isLast": True,
            "values": [MOCK_BOARD_API_RESPONSE],
        }

        batches = []
        async for batch in mock_jira_client._get_agile_paginated_data(
            url="https://exampleorg.atlassian.net/rest/agile/1.0/board"
        ):
            batches.append(batch)

        assert len(batches) == 1
        assert batches[0] == [MOCK_BOARD_API_RESPONSE]
        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_agile_paginator_stops_on_empty_items(
    mock_jira_client: JiraClient,
) -> None:
    """Paginator must stop immediately when values list is empty."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "startAt": 0,
            "maxResults": 50,
            "total": 0,
            "isLast": False,
            "values": [],
        }

        batches = []
        async for batch in mock_jira_client._get_agile_paginated_data(
            url="https://exampleorg.atlassian.net/rest/agile/1.0/board"
        ):
            batches.append(batch)

        assert len(batches) == 0
        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_agile_paginator_handles_missing_is_last(
    mock_jira_client: JiraClient,
) -> None:
    """If isLast is absent, paginator must not loop forever.
    It should stop after the first page that returns fewer items than maxResults.
    """
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
            # isLast deliberately absent
            "values": [MOCK_BOARD_API_RESPONSE],
        }

        batches = []
        async for batch in mock_jira_client._get_agile_paginated_data(
            url="https://exampleorg.atlassian.net/rest/agile/1.0/board"
        ):
            batches.append(batch)

        assert len(batches) == 1
        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_agile_paginator_paginates_across_multiple_pages(
    mock_jira_client: JiraClient,
) -> None:
    """Paginator must continue fetching until isLast is True."""
    page_1 = {
        "startAt": 0,
        "maxResults": 1,
        "total": 2,
        "isLast": False,
        "values": [MOCK_BOARD_API_RESPONSE],
    }
    page_2 = {
        "startAt": 1,
        "maxResults": 1,
        "total": 2,
        "isLast": True,
        "values": [{**MOCK_BOARD_API_RESPONSE, "id": 2, "name": "Second board"}],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [page_1, page_2]

        batches = []
        async for batch in mock_jira_client._get_agile_paginated_data(
            url="https://exampleorg.atlassian.net/rest/agile/1.0/board"
        ):
            batches.append(batch)

        assert len(batches) == 2
        assert mock_request.call_count == 2
        assert batches[0][0]["id"] == 1
        assert batches[1][0]["id"] == 2


@pytest.mark.asyncio
async def test_get_paginated_boards_passes_type_param(
    mock_jira_client: JiraClient,
) -> None:
    """board_type selector must be passed as 'type' query param to the API."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [MOCK_BOARD_API_RESPONSE],
        }

        async for _ in mock_jira_client.get_paginated_boards(params={"type": "scrum"}):
            pass

        call_params = (
            mock_request.call_args[1].get("params") or mock_request.call_args[0][2]
        )
        assert call_params.get("type") == "scrum"


@pytest.mark.asyncio
async def test_get_paginated_boards_omits_none_params(
    mock_jira_client: JiraClient,
) -> None:
    """None selector fields must not appear in the API request params."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [MOCK_BOARD_API_RESPONSE],
        }

        async for _ in mock_jira_client.get_paginated_boards(params={}):
            pass

        call_params = (
            mock_request.call_args[1].get("params") or mock_request.call_args[0][2]
        )
        assert "type" not in call_params
        assert "projectKeyOrId" not in call_params


@pytest.mark.asyncio
async def test_get_paginated_boards_returns_boards_with_admins(
    mock_jira_client: JiraClient,
) -> None:
    """Boards with admins object must be returned as-is for mapping layer."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [MOCK_BOARD_WITH_ADMINS],
        }

        batches = []
        async for batch in mock_jira_client.get_paginated_boards():
            batches.append(batch)

        assert len(batches) == 1
        board = batches[0][0]
        assert "admins" in board
        assert len(board["admins"]["users"]) == 2
        assert len(board["admins"]["groups"]) == 2


@pytest.mark.asyncio
async def test_get_paginated_boards_returns_boards_without_admins(
    mock_jira_client: JiraClient,
) -> None:
    """Boards without admins field must be returned as-is — mapping layer handles null safely."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [MOCK_BOARD_WITHOUT_ADMINS],
        }

        batches = []
        async for batch in mock_jira_client.get_paginated_boards():
            batches.append(batch)

        assert len(batches) == 1
        board = batches[0][0]
        assert "admins" not in board


@pytest.mark.asyncio
async def test_get_paginated_boards_returns_boards_with_null_account_ids(
    mock_jira_client: JiraClient,
) -> None:
    """Boards with null accountIds in admins.users must still be returned —
    the mapping layer filters null accountIds via select(.accountId != null)."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [MOCK_BOARD_WITH_NULL_ACCOUNT_IDS],
        }

        batches = []
        async for batch in mock_jira_client.get_paginated_boards():
            batches.append(batch)

        assert len(batches) == 1
        board = batches[0][0]
        # Raw data is returned intact — mapping layer does the filtering
        assert board["admins"]["users"][0]["accountId"] is None
        assert board["admins"]["users"][1]["accountId"] == "abc123"


@pytest.mark.asyncio
async def test_successfully_resolves_agile_url_for_basic_auth(
    mock_jira_client: JiraClient,
) -> None:
    agile_url = await mock_jira_client._get_agile_api_url()
    assert agile_url == f"{mock_jira_client.jira_rest_url}/agile/1.0"


@pytest.mark.asyncio
async def test_successfully_resolves_agile_url_for_oauth(
    mock_jira_client: JiraClient,
) -> None:
    mock_cloud_id = "33f08530-afd8-42fd-82cc-1dd5ebfeece8"

    with patch.object(mock_jira_client, "is_oauth_enabled", return_value=True):
        mock_jira_client._agile_api_url = None
        with patch.object(
            mock_jira_client, "_get_cloud_id", new_callable=AsyncMock
        ) as mock_get_cloud_id:
            mock_get_cloud_id.return_value = mock_cloud_id
            agile_url = await mock_jira_client._get_agile_api_url()

    assert (
        agile_url
        == f"https://api.atlassian.com/ex/jira/{mock_cloud_id}/rest/agile/latest"
    )


@pytest.mark.asyncio
async def test_successfully_resolves_agile_url_for_oauth_uses_cache_on_subsequent_calls(
    mock_jira_client: JiraClient,
) -> None:
    """_get_agile_api_url must only resolve cloud ID once — subsequent calls use cache."""
    mock_cloud_id = "33f08530-afd8-42fd-82cc-1dd5ebfeece8"

    with patch.object(
        mock_jira_client, "_get_cloud_id", new_callable=AsyncMock
    ) as mock_get_cloud_id:
        mock_get_cloud_id.return_value = mock_cloud_id
        mock_jira_client._agile_api_url = None

        await mock_jira_client._get_agile_api_url()
        await mock_jira_client._get_agile_api_url()
        await mock_jira_client._get_agile_api_url()

    mock_get_cloud_id.assert_called_once()


@pytest.mark.asyncio
async def test_can_successfully_get_cloud_id_for_oauth(
    mock_jira_client: JiraClient,
) -> None:
    mock_resources = [
        {
            "id": "33f08530-afd8-42fd-82cc-1dd5ebfeece8",
            "url": "https://example.atlassian.net",
            "name": "example",
            "scopes": ["read:board-scope:jira-software"],
            "avatarUrl": "https://cdn.example.com/avatar.png",
        }
    ]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_resources

        cloud_id = await mock_jira_client._get_cloud_id()

    assert cloud_id == "33f08530-afd8-42fd-82cc-1dd5ebfeece8"
    mock_request.assert_called_once_with(
        "GET",
        "https://api.atlassian.com/oauth/token/accessible-resources",
    )


@pytest.mark.asyncio
async def test_get_cloud_id_raises_value_error_when_jira_url_not_in_accessible_resources(
    mock_jira_client: JiraClient,
) -> None:
    """_get_cloud_id must raise ValueError if none of the accessible resources
    match the configured jira_url — prevents silent misconfiguration."""
    mock_resources = [
        {
            "id": "some-other-cloud-id",
            "url": "https://completely-different-org.atlassian.net",
            "name": "other",
            "scopes": [],
            "avatarUrl": "",
        }
    ]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_resources

        with pytest.raises(ValueError, match="Could not resolve cloud ID"):
            await mock_jira_client._get_cloud_id()


@pytest.mark.asyncio
async def test_get_cloud_id_handles_trailing_slash_in_jira_url(
    mock_jira_client: JiraClient,
) -> None:
    """URL comparison must be slash-normalized — trailing slashes must not cause a mismatch."""
    mock_resources = [
        {
            "id": "33f08530-afd8-42fd-82cc-1dd5ebfeece8",
            "url": "https://example.atlassian.net/",
            "name": "example",
            "scopes": [],
            "avatarUrl": "",
        }
    ]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_resources

        cloud_id = await mock_jira_client._get_cloud_id()

    assert cloud_id == "33f08530-afd8-42fd-82cc-1dd5ebfeece8"


@pytest.mark.asyncio
async def test_get_cloud_id_raises_when_accessible_resources_returns_empty_list(
    mock_jira_client: JiraClient,
) -> None:
    """Empty accessible-resources response must raise ValueError, not IndexError."""
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = []

        with pytest.raises(ValueError, match="Could not resolve cloud ID"):
            await mock_jira_client._get_cloud_id()


@pytest.mark.asyncio
async def test_get_cloud_id_extracts_from_gateway_url_without_api_call(
    mock_jira_client: JiraClient,
) -> None:
    """When jira_url is already in gateway format, cloud ID must be extracted
    directly without making an accessible-resources API call."""
    mock_jira_client.jira_url = (
        "https://api.atlassian.com/ex/jira/33f08530-afd8-42fd-82cc-1dd5ebfeece8"
    )

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        cloud_id = await mock_jira_client._get_cloud_id()

    assert cloud_id == "33f08530-afd8-42fd-82cc-1dd5ebfeece8"
    mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_get_cloud_id_extracts_from_gateway_url_with_trailing_slash(
    mock_jira_client: JiraClient,
) -> None:
    """Trailing slash on gateway jira_url must not break cloud ID extraction."""
    mock_jira_client.jira_url = (
        "https://api.atlassian.com/ex/jira/33f08530-afd8-42fd-82cc-1dd5ebfeece8/"
    )

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        cloud_id = await mock_jira_client._get_cloud_id()

    assert cloud_id == "33f08530-afd8-42fd-82cc-1dd5ebfeece8"
    mock_request.assert_not_called()


@pytest.mark.asyncio
async def test_get_cloud_id_falls_back_to_accessible_resources_for_non_gateway_url(
    mock_jira_client: JiraClient,
) -> None:
    """When jira_url is a direct site URL, cloud ID must be resolved
    via the accessible-resources endpoint."""
    mock_resources = [
        {
            "id": "33f08530-afd8-42fd-82cc-1dd5ebfeece8",
            "url": "https://example.atlassian.net",
            "name": "example",
            "scopes": [],
            "avatarUrl": "",
        }
    ]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_resources
        cloud_id = await mock_jira_client._get_cloud_id()

    assert cloud_id == "33f08530-afd8-42fd-82cc-1dd5ebfeece8"
    mock_request.assert_called_once_with(
        "GET",
        "https://api.atlassian.com/oauth/token/accessible-resources",
    )


@pytest.mark.asyncio
async def test_get_board_projects_returns_projects_for_board(
    mock_jira_client: JiraClient,
) -> None:
    mock_projects_response = {
        "isLast": True,
        "maxResults": 50,
        "startAt": 0,
        "total": 2,
        "values": [
            {"id": "10000", "key": "PORT", "name": "Port"},
            {"id": "10001", "key": "DEMO", "name": "Demo"},
        ],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_projects_response

        project_batches = []
        async for batch in mock_jira_client.get_board_projects(board_id=1):
            project_batches.append(batch)

    assert len(project_batches) == 1
    assert len(project_batches[0]) == 2
    assert project_batches[0][0]["key"] == "PORT"
    assert project_batches[0][1]["key"] == "DEMO"


@pytest.mark.asyncio
async def test_get_board_projects_returns_empty_when_no_projects(
    mock_jira_client: JiraClient,
) -> None:
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "maxResults": 50,
            "startAt": 0,
            "total": 0,
            "values": [],
        }

        project_batches = []
        async for batch in mock_jira_client.get_board_projects(board_id=1):
            project_batches.append(batch)

    assert len(project_batches) == 0


@pytest.mark.asyncio
async def test_enrich_board_with_projects_injects_project_keys(
    mock_jira_client: JiraClient,
) -> None:
    board = {**MOCK_BOARD_API_RESPONSE}
    mock_projects_response = {
        "isLast": True,
        "values": [
            {"id": "10000", "key": "PORT", "name": "Port"},
            {"id": "10001", "key": "DEMO", "name": "Demo"},
        ],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_projects_response

        enriched = await mock_jira_client.enrich_board_with_projects(board)

    assert "__projectKeys" in enriched
    assert enriched["__projectKeys"] == ["PORT", "DEMO"]


@pytest.mark.asyncio
async def test_enrich_board_with_projects_returns_empty_list_when_no_projects(
    mock_jira_client: JiraClient,
) -> None:
    board = {**MOCK_BOARD_API_RESPONSE}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [],
        }

        enriched = await mock_jira_client.enrich_board_with_projects(board)

    assert enriched["__projectKeys"] == []


@pytest.mark.asyncio
async def test_enrich_board_with_projects_skips_projects_with_missing_key(
    mock_jira_client: JiraClient,
) -> None:
    """Projects missing the key field must be skipped — guards against malformed API responses."""
    board = {**MOCK_BOARD_API_RESPONSE}
    mock_projects_response = {
        "isLast": True,
        "values": [
            {"id": "10000", "key": "PORT", "name": "Port"},
            {"id": "10001", "name": "Broken project"},  # key absent
            {"id": "10002", "key": None, "name": "Null key project"},  # key is None
        ],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = mock_projects_response

        enriched = await mock_jira_client.enrich_board_with_projects(board)

    assert enriched["__projectKeys"] == ["PORT"]


@pytest.mark.asyncio
async def test_get_paginated_boards_enriches_boards_with_project_keys(
    mock_jira_client: JiraClient,
) -> None:
    """Resync handler must enrich each board batch with project keys concurrently."""
    boards_response = {
        "isLast": True,
        "values": [MOCK_BOARD_API_RESPONSE],
    }
    projects_response = {
        "isLast": True,
        "values": [
            {"id": "10000", "key": "PORT", "name": "Port"},
        ],
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [boards_response, projects_response]

        batches = []
        async for batch in mock_jira_client.get_paginated_boards():
            # Simulate what resync handler does
            enriched = await asyncio.gather(
                *[mock_jira_client.enrich_board_with_projects(b) for b in batch]
            )
            batches.append(list(enriched))

    assert len(batches) == 1
    assert batches[0][0]["__projectKeys"] == ["PORT"]


@pytest.mark.asyncio
async def test_enrich_board_with_projects_does_not_mutate_original_board_reference(
    mock_jira_client: JiraClient,
) -> None:
    """enrich_board_with_projects mutates the board dict in place —
    verify __projectKeys is injected on the same object returned."""
    board = {**MOCK_BOARD_API_RESPONSE}
    original_id = id(board)

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = {
            "isLast": True,
            "values": [{"id": "10000", "key": "PORT", "name": "Port"}],
        }

        enriched = await mock_jira_client.enrich_board_with_projects(board)

    assert id(enriched) == original_id
    assert "__projectKeys" in board


@pytest.mark.asyncio
async def test_enrich_board_with_projects_returns_empty_list_when_board_has_no_id(
    mock_jira_client: JiraClient,
) -> None:
    board: dict[str, Any] = {"name": "Broken board"}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        enriched = await mock_jira_client.enrich_board_with_projects(board)

    assert enriched["__projectKeys"] == []
    mock_request.assert_not_called()
