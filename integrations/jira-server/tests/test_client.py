from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import BasicAuth, Request, Response
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira_server.client import JiraServerClient


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Fixture to mock the Ocean context initialization."""
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "jira_server_url": "https://jira.example.com",
            "jira_server_username": "admin",
            "jira_server_password": "password",
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_jira_server_client() -> JiraServerClient:
    """Fixture to initialize JiraServerClient with mock parameters."""
    return JiraServerClient(
        server_url="https://jira.example.com",
        username="admin",
        password="password",
    )


@pytest.mark.asyncio
async def test_client_initialization(mock_jira_server_client: JiraServerClient) -> None:
    """Test JiraServerClient initialization."""
    assert mock_jira_server_client.api_url == "https://jira.example.com/rest/api/2"
    assert isinstance(mock_jira_server_client.client.auth, BasicAuth)


@pytest.mark.asyncio
async def test_send_api_request_success(
    mock_jira_server_client: JiraServerClient,
) -> None:
    """Test successful API requests."""
    with patch.object(
        mock_jira_server_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            200, request=Request("GET", "http://example.com"), json={"key": "value"}
        )
        response = await mock_jira_server_client._send_api_request(
            "GET", "http://example.com"
        )
        assert response["key"] == "value"


@pytest.mark.asyncio
async def test_send_api_request_failure(
    mock_jira_server_client: JiraServerClient,
) -> None:
    """Test API request raising exceptions."""
    with patch.object(
        mock_jira_server_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = Response(
            404, request=Request("GET", "http://example.com")
        )
        with pytest.raises(Exception):
            await mock_jira_server_client._send_api_request("GET", "http://example.com")


@pytest.mark.asyncio
async def test_get_single_project(mock_jira_server_client: JiraServerClient) -> None:
    """Test get_single_project method."""
    project_data = {"key": "PROJ", "name": "Project Name"}

    with patch.object(
        mock_jira_server_client.client, "get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = Response(
            200, request=Request("GET", "http://example.com"), json=project_data
        )
        result = await mock_jira_server_client.get_single_project("PROJ")

        mock_get.assert_called_once_with(
            f"{mock_jira_server_client.api_url}/project/PROJ"
        )
        assert result == project_data


@pytest.mark.asyncio
async def test_get_single_issue(mock_jira_server_client: JiraServerClient) -> None:
    """Test get_single_issue method."""
    issue_data = {"key": "PROJ-1", "fields": {"summary": "Test issue"}}

    with patch.object(
        mock_jira_server_client.client, "get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = Response(
            200, request=Request("GET", "http://example.com"), json=issue_data
        )
        result = await mock_jira_server_client.get_single_issue("PROJ-1")

        mock_get.assert_called_once_with(
            f"{mock_jira_server_client.api_url}/issue/PROJ-1"
        )
        assert result == issue_data


@pytest.mark.asyncio
async def test_get_single_user(mock_jira_server_client: JiraServerClient) -> None:
    """Test get_single_user method."""
    user_data = {"accountId": "user1", "emailAddress": "user@example.com"}

    with patch.object(
        mock_jira_server_client.client, "get", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = Response(
            200, request=Request("GET", "http://example.com"), json=user_data
        )
        result = await mock_jira_server_client.get_single_user("user1")

        mock_get.assert_called_once_with(
            f"{mock_jira_server_client.api_url}/user", params={"username": "user1"}
        )
        assert result == user_data


@pytest.mark.asyncio
async def test_get_all_projects(mock_jira_server_client: JiraServerClient) -> None:
    """Test get_all_projects method."""
    projects_data = [{"key": "PROJ1"}, {"key": "PROJ2"}]

    with patch.object(
        mock_jira_server_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = projects_data
        result = await mock_jira_server_client.get_all_projects()

        mock_request.assert_called_once_with(
            "GET", f"{mock_jira_server_client.api_url}/project"
        )
        assert result == projects_data


@pytest.mark.asyncio
async def test_get_paginated_issues(mock_jira_server_client: JiraServerClient) -> None:
    """Test paginated fetching of issues."""
    issues_data_page1 = {"issues": [{"key": "ISSUE-1"}], "total": 2}
    issues_data_page2 = {"issues": [{"key": "ISSUE-2"}], "total": 2}

    with patch.object(
        mock_jira_server_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [
            issues_data_page1,
            issues_data_page2,
            {"issues": []},
        ]

        issues = []
        async for issue_batch in mock_jira_server_client.get_paginated_issues(
            params={"jql": "project = PROJ"}
        ):
            issues.extend(issue_batch)

        assert len(issues) == 2
        assert issues == [{"key": "ISSUE-1"}, {"key": "ISSUE-2"}]


@pytest.mark.asyncio
async def test_get_paginated_users(mock_jira_server_client: JiraServerClient) -> None:
    """Test paginated fetching of users."""
    users_page1 = [{"accountId": "user1"}, {"accountId": "user2"}]
    users_page2 = [{"accountId": "user3"}]

    with patch.object(
        mock_jira_server_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [users_page1, users_page2, []]

        users = []
        async for user_batch in mock_jira_server_client.get_paginated_users(
            username="testuser"
        ):
            users.extend(user_batch)

        assert len(users) == 3
        assert users == [
            {"accountId": "user1"},
            {"accountId": "user2"},
            {"accountId": "user3"},
        ]
