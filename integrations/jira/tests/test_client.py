import pytest
from httpx import AsyncClient, Response, Request
from unittest.mock import AsyncMock, patch, MagicMock
from jira.client import JiraClient, BearerAuth, BasicAuth, WEBHOOK_EVENTS, PAGE_SIZE
from jira.overrides import JiraResourceConfig, JiraPortAppConfig
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.context.event import event_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig



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
def mock_jira_client():
    """Fixture to initialize JiraClient with mock parameters."""
    return JiraClient(
        jira_url="https://example.atlassian.net",
        jira_email="test@example.com",
        jira_token="test_token",
    )


@pytest.mark.asyncio
async def test_client_initialization(mock_jira_client):
    """Test the correct initialization of JiraClient."""
    assert mock_jira_client.jira_rest_url == "https://example.atlassian.net/rest"
    assert isinstance(mock_jira_client.jira_api_auth, BasicAuth)


@pytest.mark.asyncio
async def test_send_api_request_success(mock_jira_client):
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
async def test_send_api_request_failure(mock_jira_client):
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
async def test_get_single_project(mock_jira_client):
    """Test get_single_project method"""
    project_data = {"key": "TEST", "name": "Test Project"}

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
async def test_get_paginated_projects(mock_jira_client):
    """Test get_paginated_projects method"""
    projects_data = {"values": [{"key": "PROJ1"}, {"key": "PROJ2"}], "total": 2}

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            projects_data,
            {"values": []},  # Empty response to end pagination
        ]

        projects = []
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
async def test_get_single_issue(mock_jira_client):
    """Test get_single_issue method"""
    issue_data = {"key": "TEST-1", "fields": {"summary": "Test Issue"}}

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
async def test_get_paginated_issues_with_event(mock_jira_client):
    """
    Test get_paginated_issues with an event-based resource_config.
    """
    # Mock JiraResourceConfig
    mock_config = JiraResourceConfig(
        selector=JiraResourceConfig.Selector(
            query="TEST",
            jql="project = TEST"
        )
    )

    # Patch the global `event.resource_config` in the event module
    async with event_context("test_event") as test_event:
        with patch('event.resource_config', mock_config):
                # Prepare mock JiraClient
                mock_jira_client.api_url = "https://jira.example.com"

                # Mock the paginated data generator
                async def mock_paginated_data(*args, **kwargs):
                    yield [{"key": "TEST-1"}, {"key": "TEST-2"}]

                mock_jira_client._get_paginated_data = mock_paginated_data

                # Call the method
                issues = []
                async for issue_batch in mock_jira_client.get_paginated_issues():
                    issues.extend(issue_batch)

                # Assertions
                assert len(issues) == 2
                assert issues == [{"key": "TEST-1"}, {"key": "TEST-2"}]
@pytest.mark.asyncio
async def test_get_single_user(mock_jira_client):
    """Test get_single_user method"""
    user_data = {"accountId": "test123", "emailAddress": "test@example.com"}

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
async def test_get_paginated_users(mock_jira_client):
    """Test get_paginated_users method"""
    users_data = [{"accountId": "user1"}, {"accountId": "user2"}]

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [users_data, []]  # Empty response to end pagination

        users = []
        async for user_batch in mock_jira_client.get_paginated_users():
            users.extend(user_batch)

        assert len(users) == 2
        assert users == users_data


@pytest.mark.asyncio
async def test_get_paginated_teams(mock_jira_client):
    """Test get_paginated_teams method"""
    teams_data = {
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

        teams = []
        async for team_batch in mock_jira_client.get_paginated_teams():
            teams.extend(team_batch)

        assert len(teams) == 2
        assert teams == teams_data["entities"]


@pytest.mark.asyncio
async def test_get_paginated_team_members(mock_jira_client):
    """Test get_paginated_team_members with actual API response format"""
    api_response = {
        "results": [
            {"accountId": "user1"},
            {"accountId": "user1"},
        ],
        "pageInfo": {
            "endCursor": "712020:436fbb1d-b060-49cf-97c5-ca5d6d4219c4",
            "hasNextPage": False,
        },
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = api_response

        members = []
        async for member_batch in mock_jira_client.get_paginated_team_members("team1"):
            members.extend(member_batch)

        assert len(members) == 2
        assert members == api_response["results"]


@pytest.mark.asyncio
async def test_get_paginated_team_members(mock_jira_client):
    """Test get_paginated_team_members with example API response format"""
    api_response = {
        "results": [{"accountId": "user1"}, {"accountId": "user2"}],
        "pageInfo": {"endCursor": "cursor1", "hasNextPage": False},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = api_response

        members = []
        async for member_batch in mock_jira_client.get_paginated_team_members("team1"):
            members.extend(member_batch)

        assert len(members) == 2
        assert members == api_response["results"]


@pytest.mark.asyncio
async def test_get_user_team_mapping(mock_jira_client):
    """Test get_user_team_mapping method"""
    # Mock responses for teams pagination
    teams_data_1 = {
        "entities": [{"teamId": "team1"}, {"teamId": "team2"}],
        "cursor": "teams_cursor1",
    }
    teams_data_2 = {"entities": [], "cursor": None}

    # Mock responses for team members
    team1_members = {
        "results": [{"accountId": "user1"}, {"accountId": "user2"}],
        "pageInfo": {"endCursor": "members_cursor1", "hasNextPage": False},
    }

    team2_members = {
        "results": [
            {"accountId": "user2"},  # user2 is in both teams
            {"accountId": "user3"},
        ],
        "pageInfo": {"endCursor": "members_cursor2", "hasNextPage": False},
    }

    with patch.object(
        mock_jira_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            teams_data_1,  # First teams page
            teams_data_2,  # End of teams pagination
            team1_members,  # Members for team1
            team2_members,  # Members for team2
        ]

        mapping = await mock_jira_client.get_user_team_mapping()

        # Verify the mapping
        assert isinstance(mapping, dict)
        assert mapping == {
            "user1": "team1",
            "user2": "team1",  # user2 should be mapped to team1 since it was found first
            "user3": "team2",
        }

        # Verify API was called correct number of times
        assert mock_request.call_count == 4


@pytest.mark.asyncio
async def test_create_events_webhook(mock_jira_client):
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
