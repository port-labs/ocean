from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import BasicAuth, Request, Response, HTTPStatusError
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from jira_server.client import JiraServerClient, JQL_IGNORED_ERRORS
from jira_server.helpers.utils import IgnoredError


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
        # First call simulates /user/list unsupported (404) -> fallback to /user/search
        not_found_response = Response(404, request=Request("GET", "http://example.com"))
        list_not_supported = HTTPStatusError(
            "Not Found", request=not_found_response.request, response=not_found_response
        )
        # Then legacy /user/search pages
        mock_request.side_effect = [list_not_supported, users_page1, users_page2, []]

        users = []
        async for user_batch in mock_jira_server_client.get_paginated_users():
            users.extend(user_batch)

        assert len(users) == 3
        assert users == [
            {"accountId": "user1"},
            {"accountId": "user2"},
            {"accountId": "user3"},
        ]
        # Verify that after the 404, we used /user/search
        # call_args_list[0] corresponds to the failing /user/list probe
        # subsequent calls should hit /user/search
        for call in mock_request.call_args_list[1:]:
            _, url, *_ = call.args
            assert "/user/search" in url


@pytest.mark.asyncio
async def test_get_paginated_users_via_list_success(
    mock_jira_server_client: JiraServerClient,
) -> None:
    """Test users fetch via /user/list using cursor-based pagination."""
    list_page1 = {
        "values": [{"accountId": "u1"}, {"accountId": "u2"}],
        "nextCursor": "c1",
        "isLast": False,
    }
    list_page2 = {
        "values": [{"accountId": "u3"}],
        "isLast": True,
    }

    with patch.object(
        mock_jira_server_client, "_send_api_request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [list_page1, list_page2]

        users = []
        async for batch in mock_jira_server_client.get_paginated_users():
            users.extend(batch)

        assert users == [
            {"accountId": "u1"},
            {"accountId": "u2"},
            {"accountId": "u3"},
        ]
        # Ensure only /user/list was used
        assert len(mock_request.call_args_list) == 2
        for call in mock_request.call_args_list:
            _, url, *_ = call.args
            assert "/user/list" in url


# ============================================================================
# Ignored Error Tests (PORT-17194)
# ============================================================================


class TestShouldIgnoreError:
    """Tests for the _should_ignore_error method."""

    def test_should_ignore_error_returns_true_when_status_matches(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that _should_ignore_error returns True when status code matches."""
        error_response = Response(400, request=Request("GET", "http://example.com"))
        error = HTTPStatusError(
            "Bad Request", request=error_response.request, response=error_response
        )
        ignored_errors = [IgnoredError(status=400, message="Test error")]

        result = mock_jira_server_client._should_ignore_error(
            error, "http://example.com", "GET", ignored_errors
        )

        assert result is True

    def test_should_ignore_error_returns_false_when_status_does_not_match(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that _should_ignore_error returns False when status code doesn't match."""
        error_response = Response(500, request=Request("GET", "http://example.com"))
        error = HTTPStatusError(
            "Server Error", request=error_response.request, response=error_response
        )
        ignored_errors = [IgnoredError(status=400, message="Test error")]

        result = mock_jira_server_client._should_ignore_error(
            error, "http://example.com", "GET", ignored_errors
        )

        assert result is False

    def test_should_ignore_error_returns_false_when_no_ignored_errors(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that _should_ignore_error returns False when ignored_errors is None."""
        error_response = Response(400, request=Request("GET", "http://example.com"))
        error = HTTPStatusError(
            "Bad Request", request=error_response.request, response=error_response
        )

        result = mock_jira_server_client._should_ignore_error(
            error, "http://example.com", "GET", None
        )

        assert result is False

    def test_should_ignore_error_handles_string_status_comparison(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that status comparison works with string status codes."""
        error_response = Response(400, request=Request("GET", "http://example.com"))
        error = HTTPStatusError(
            "Bad Request", request=error_response.request, response=error_response
        )
        # Status as string should still match
        ignored_errors = [IgnoredError(status="400", message="Test error")]

        result = mock_jira_server_client._should_ignore_error(
            error, "http://example.com", "GET", ignored_errors
        )

        assert result is True


class TestSendApiRequestWithIgnoredErrors:
    """Tests for _send_api_request with ignored_errors parameter."""

    @pytest.mark.asyncio
    async def test_send_api_request_returns_empty_dict_for_ignored_error(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that _send_api_request returns {} when error is ignored."""
        with patch.object(
            mock_jira_server_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = Response(
                400, request=Request("GET", "http://example.com")
            )
            ignored_errors = [IgnoredError(status=400, message="Test ignored error")]

            result = await mock_jira_server_client._send_api_request(
                "GET", "http://example.com", ignored_errors=ignored_errors
            )

            assert result == {}

    @pytest.mark.asyncio
    async def test_send_api_request_raises_for_non_ignored_error(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that _send_api_request raises when error is not in ignored list."""
        with patch.object(
            mock_jira_server_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = Response(
                500, request=Request("GET", "http://example.com")
            )
            ignored_errors = [IgnoredError(status=400, message="Only 400 ignored")]

            with pytest.raises(HTTPStatusError):
                await mock_jira_server_client._send_api_request(
                    "GET", "http://example.com", ignored_errors=ignored_errors
                )

    @pytest.mark.asyncio
    async def test_send_api_request_raises_when_no_ignored_errors_provided(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that _send_api_request raises for 400 when no ignored_errors provided."""
        with patch.object(
            mock_jira_server_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = Response(
                400, request=Request("GET", "http://example.com")
            )

            with pytest.raises(HTTPStatusError):
                await mock_jira_server_client._send_api_request(
                    "GET", "http://example.com"
                )


class TestGetPaginatedIssuesWithIgnoredErrors:
    """Tests for get_paginated_issues handling of JQL 400 errors (PORT-17194)."""

    @pytest.mark.asyncio
    async def test_get_paginated_issues_handles_400_jql_error_gracefully(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that 400 errors from JQL queries are ignored and return no issues.

        This tests the fix for PORT-17194 where JQL queries referencing
        inaccessible projects return 400 errors and should not crash the resync.
        """
        with patch.object(
            mock_jira_server_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            # Simulate Jira returning 400 for inaccessible project in JQL
            mock_request.return_value = Response(
                400, request=Request("GET", "http://example.com/search")
            )

            issues = []
            async for issue_batch in mock_jira_server_client.get_paginated_issues(
                params={"jql": "project = INACCESSIBLE_PROJECT"}
            ):
                issues.extend(issue_batch)

            # Should return empty list, not raise exception
            assert issues == []

    @pytest.mark.asyncio
    async def test_get_paginated_issues_uses_jql_ignored_errors(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that get_paginated_issues passes JQL_IGNORED_ERRORS to _send_api_request."""
        with patch.object(
            mock_jira_server_client, "_send_api_request", new_callable=AsyncMock
        ) as mock_request:
            # Return empty response to stop pagination
            mock_request.return_value = {}

            issues = []
            async for issue_batch in mock_jira_server_client.get_paginated_issues():
                issues.extend(issue_batch)

            # Verify _send_api_request was called with ignored_errors
            call_kwargs = mock_request.call_args.kwargs
            assert "ignored_errors" in call_kwargs
            assert call_kwargs["ignored_errors"] == JQL_IGNORED_ERRORS

    @pytest.mark.asyncio
    async def test_get_paginated_issues_still_raises_non_400_errors(
        self, mock_jira_server_client: JiraServerClient
    ) -> None:
        """Test that non-400 errors are still raised by get_paginated_issues."""
        with patch.object(
            mock_jira_server_client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            # Simulate 500 server error (should not be ignored)
            mock_request.return_value = Response(
                500, request=Request("GET", "http://example.com/search")
            )

            with pytest.raises(HTTPStatusError):
                async for _ in mock_jira_server_client.get_paginated_issues():
                    pass
