import pytest
from typing import List, Dict, Any
from httpx import BasicAuth, Response, Request
from unittest.mock import AsyncMock, patch, MagicMock
from jira.client import JiraClient, WEBHOOK_EVENTS, PAGE_SIZE
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.event import event_context


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "jira_host": "https://getport.atlassian.net",
            "atlassian_user_email": "jira@atlassian.net",
            "atlassian_user_token": "asdf",
            "atlassian_organisation_id": "asdf",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
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
    project_data: Dict[str, Any] = {"key": "TEST", "name": "Test Project"}

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
    projects_data: Dict[str, Any] = {
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

        projects: List[Dict[str, Any]] = []
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
    issue_data: Dict[str, Any] = {"key": "TEST-1", "fields": {"summary": "Test Issue"}}

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
    """Test get_paginated_issues with JQL filtering"""

    # Mock response data
    issues_data = {"issues": [{"key": "TEST-1"}, {"key": "TEST-2"}], "total": 2}

    # Mock config for JQL
    mock_config = MagicMock()
    mock_config.selector.jql = "project = TEST"

    # Mock the port app config needed for event_context
    mock_port_app_config = MagicMock()

    async with event_context(
        "test_event",
        trigger_type="manual",
        attributes={},
    ) as test_event:
        # Set the port app config on the event context
        test_event._port_app_config = mock_port_app_config

        # Import and use resource_context
        from port_ocean.context.resource import resource_context

        async with resource_context(mock_config):
            with patch.object(
                mock_jira_client, "_send_api_request", new_callable=AsyncMock
            ) as mock_request:
                mock_request.side_effect = [issues_data, {"issues": []}]

                issues = []
                async for issue_batch in mock_jira_client.get_paginated_issues():
                    issues.extend(issue_batch)

                assert len(issues) == 2
                assert issues == issues_data["issues"]

                # Verify JQL was passed correctly
                mock_request.assert_called_with(
                    "GET",
                    f"{mock_jira_client.api_url}/search",
                    params={
                        "jql": "project = TEST",
                        "maxResults": PAGE_SIZE,
                        "startAt": 0,
                    },
                )


@pytest.mark.asyncio
async def test_get_single_user(mock_jira_client: JiraClient) -> None:
    """Test get_single_user method"""
    user_data: Dict[str, Any] = {
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
    users_data: List[Dict[str, Any]] = [{"accountId": "user1"}, {"accountId": "user2"}]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [users_data, []]  # Empty response to end pagination

        users: List[Dict[str, Any]] = []
        async for user_batch in mock_jira_client.get_paginated_users():
            users.extend(user_batch)

        assert len(users) == 2
        assert users == users_data


@pytest.mark.asyncio
async def test_get_paginated_teams(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_teams method"""
    teams_data: Dict[str, Any] = {
        "entities": [{"teamId": "team1"}, {"teamId": "team2"}],
        "cursor": None,
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            teams_data,
            {"entities": []},  # Empty response to end pagination
        ]

        teams: List[Dict[str, Any]] = []
        async for team_batch in mock_jira_client.get_paginated_teams("test_org_id"):
            teams.extend(team_batch)

        assert len(teams) == 2
        assert teams == teams_data["entities"]


@pytest.mark.asyncio
async def test_get_paginated_team_members(mock_jira_client: JiraClient) -> None:
    """Test get_paginated_team_members with example API response format"""
    api_response: Dict[str, Any] = {
        "results": [{"accountId": "user1"}, {"accountId": "user2"}],
        "pageInfo": {"endCursor": "cursor1", "hasNextPage": False},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = api_response

        members: List[Dict[str, Any]] = []
        async for member_batch in mock_jira_client.get_paginated_team_members("team1"):
            members.extend(member_batch)

        assert len(members) == 2
        assert members == api_response["results"]


@pytest.mark.asyncio
async def get_user_team_mapping(self, org_id: str) -> Dict[str, List[str]]:

    user_team_mapping = {}

    teams = []
    async for team_batch in self.get_paginated_teams(org_id):
        teams.extend(team_batch)

    logger.info(f"Processing {len(teams)} teams for user mapping")

    # Process teams in the order they were received
    for team in teams:
        team_id = team["teamId"]
        async for members in self.get_paginated_team_members(team_id):
            for member in members:
                account_id = member["accountId"]
                if account_id not in user_team_mapping:
                    user_team_mapping[account_id] = []
                # Add the team to the user's list
                if team_id not in user_team_mapping[account_id]:
                    user_team_mapping[account_id].append(team_id)

    logger.info(f"Created mapping for {len(user_team_mapping)} users")
    return user_team_mapping

@pytest.mark.asyncio
async def test_create_events_webhook(mock_jira_client: JiraClient) -> None:
    """Test create_events_webhook method"""
    app_host = "https://example.com"
    webhook_url = f"{app_host}/integration/webhook"

    # Test when webhook doesn't exist
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            [],  # No existing webhooks
            {"id": "new_webhook"},  # Creation response
        ]

        await mock_jira_client.create_events_webhook(app_host)

        # Verify webhook creation call
        create_call = mock_request.call_args_list[1]
        assert create_call[0][0] == "POST"
        assert create_call[0][1] == mock_jira_client.webhooks_url
        assert create_call[1]["json"]["url"] == webhook_url
        assert create_call[1]["json"]["events"] == WEBHOOK_EVENTS

    # Test when webhook already exists
    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = [{"url": webhook_url}]

        await mock_jira_client.create_events_webhook(app_host)
        mock_request.assert_called_once()  # Only checks for existence
