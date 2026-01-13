"""Unit tests for the Sentry client."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from clients.exceptions import IgnoredError, ResourceNotFoundError
from clients.sentry import SentryClient, flatten_list


pytestmark = pytest.mark.asyncio


@pytest.fixture
def sentry_client() -> SentryClient:
    """Provides a SentryClient instance for testing."""
    return SentryClient(
        sentry_base_url="https://sentry.io",
        auth_token="test-token",
        sentry_organization="test-org",
    )


@pytest.fixture
def mock_response() -> MagicMock:
    """Provides a mock httpx.Response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.headers = httpx.Headers({})
    response.json.return_value = []
    return response


class TestFlattenList:
    """Tests for the flatten_list helper function."""

    def test_flatten_nested_lists(self) -> None:
        """Tests flattening of nested lists."""
        nested = [[1, 2], [3, 4], [5, 6]]
        result = flatten_list(nested)
        assert result == [1, 2, 3, 4, 5, 6]

    def test_flatten_empty_list(self) -> None:
        """Tests flattening of an empty list."""
        assert flatten_list([]) == []

    def test_flatten_single_element_lists(self) -> None:
        """Tests flattening of single-element nested lists."""
        nested = [[1], [2], [3]]
        result = flatten_list(nested)
        assert result == [1, 2, 3]

    def test_flatten_empty_nested_lists(self) -> None:
        """Tests flattening with some empty nested lists."""
        nested = [[1, 2], [], [3, 4]]
        result = flatten_list(nested)
        assert result == [1, 2, 3, 4]


class TestSentryClientInit:
    """Tests for SentryClient initialization."""

    def test_client_initialization(self, sentry_client: SentryClient) -> None:
        """Tests correct initialization of SentryClient."""
        assert sentry_client.sentry_base_url == "https://sentry.io"
        assert sentry_client.auth_token == "test-token"
        assert sentry_client.organization == "test-org"
        assert sentry_client.api_url == "https://sentry.io/api/0"
        assert sentry_client.base_headers == {"Authorization": "Bearer test-token"}


class TestGetNextLink:
    """Tests for the get_next_link static method."""

    def test_returns_next_url_when_results_true(self) -> None:
        """Tests extraction of next URL from link header."""
        link_header = (
            '<https://sentry.io/api/0/projects/?cursor=123>; rel="previous"; results="true", '
            '<https://sentry.io/api/0/projects/?cursor=456>; rel="next"; results="true"'
        )
        result = SentryClient.get_next_link(link_header)
        assert result == "https://sentry.io/api/0/projects/?cursor=456"

    def test_returns_empty_when_no_more_results(self) -> None:
        """Tests that empty string is returned when no more results."""
        link_header = (
            '<https://sentry.io/api/0/projects/?cursor=123>; rel="previous"; results="true", '
            '<https://sentry.io/api/0/projects/?cursor=456>; rel="next"; results="false"'
        )
        result = SentryClient.get_next_link(link_header)
        assert result == ""

    def test_returns_empty_for_empty_header(self) -> None:
        """Tests that empty string is returned for empty header."""
        assert SentryClient.get_next_link("") == ""

    def test_returns_empty_for_no_next_link(self) -> None:
        """Tests that empty string is returned when there's no next link."""
        link_header = '<https://sentry.io/api/0/projects/?cursor=123>; rel="previous"; results="true"'
        result = SentryClient.get_next_link(link_header)
        assert result == ""


class TestShouldIgnoreError:
    """Tests for the _should_ignore_error method."""

    def test_ignores_401_error(self, sentry_client: SentryClient) -> None:
        """Tests that 401 errors are ignored by default."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 401
        error = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=response
        )

        result = sentry_client._should_ignore_error(error, "/test-resource")
        assert result is True

    def test_ignores_403_error(self, sentry_client: SentryClient) -> None:
        """Tests that 403 errors are ignored by default."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        error = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=response
        )

        result = sentry_client._should_ignore_error(error, "/test-resource")
        assert result is True

    def test_does_not_ignore_500_error(self, sentry_client: SentryClient) -> None:
        """Tests that 500 errors are not ignored."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 500
        error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=response
        )

        result = sentry_client._should_ignore_error(error, "/test-resource")
        assert result is False

    def test_ignores_custom_error(self, sentry_client: SentryClient) -> None:
        """Tests that custom ignored errors are handled."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 429
        error = httpx.HTTPStatusError(
            "Too Many Requests", request=MagicMock(), response=response
        )

        custom_ignored = [IgnoredError(status=429, message="Rate limited")]
        result = sentry_client._should_ignore_error(
            error, "/test-resource", custom_ignored
        )
        assert result is True


class TestSendApiRequest:
    """Tests for the send_api_request method."""

    async def test_successful_request(self, sentry_client: SentryClient) -> None:
        """Tests a successful API request."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            response = await sentry_client.send_api_request("GET", "/test")
            assert response == mock_response
            mock_request.assert_awaited_once_with(
                "GET",
                "https://sentry.io/api/0/test",
                params=None,
                headers={"Authorization": "Bearer test-token"},
            )

    async def test_request_with_full_url(self, sentry_client: SentryClient) -> None:
        """Tests API request with a full URL."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            await sentry_client.send_api_request(
                "GET", "https://custom.sentry.io/api/0/test"
            )
            mock_request.assert_awaited_once_with(
                "GET",
                "https://custom.sentry.io/api/0/test",
                params=None,
                headers={"Authorization": "Bearer test-token"},
            )

    async def test_request_raises_resource_not_found_on_404(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that 404 errors raise ResourceNotFoundError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(ResourceNotFoundError):
                await sentry_client.send_api_request("GET", "/missing-resource")

    async def test_request_returns_empty_response_for_ignored_errors(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that ignored errors return an empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await sentry_client.send_api_request(
                "GET", "/protected-resource"
            )
            assert response.status_code == 200
            assert response.content == b"{}"

    async def test_request_reraises_non_ignored_errors(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that non-ignored errors are re-raised."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await sentry_client.send_api_request("GET", "/error-resource")


class TestGetPaginatedResource:
    """Tests for the _get_paginated_resource method."""

    async def test_fetches_single_page(self, sentry_client: SentryClient) -> None:
        """Tests fetching a single page of results."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            results = []
            async for page in sentry_client._get_paginated_resource("/test"):
                results.extend(page)

            assert results == [{"id": 1}, {"id": 2}]

    async def test_fetches_multiple_pages(self, sentry_client: SentryClient) -> None:
        """Tests fetching multiple pages of results."""
        mock_response_page_1 = MagicMock(spec=httpx.Response)
        mock_response_page_1.json.return_value = [{"id": 1}]
        mock_response_page_1.headers = httpx.Headers(
            {
                "link": '<https://sentry.io/api/0/test?cursor=abc>; rel="next"; results="true"'
            }
        )
        mock_response_page_1.status_code = 200
        mock_response_page_1.raise_for_status = MagicMock()

        mock_response_page_2 = MagicMock(spec=httpx.Response)
        mock_response_page_2.json.return_value = [{"id": 2}]
        mock_response_page_2.headers = httpx.Headers({})
        mock_response_page_2.status_code = 200
        mock_response_page_2.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            side_effect=[mock_response_page_1, mock_response_page_2],
        ):
            results = []
            async for page in sentry_client._get_paginated_resource("/test"):
                results.extend(page)

            assert results == [{"id": 1}, {"id": 2}]


class TestGetTags:
    """Tests for the _get_tags method."""

    async def test_returns_tags_on_success(self, sentry_client: SentryClient) -> None:
        """Tests successful retrieval of tags."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"key": "env", "value": "production"}]
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            tags = await sentry_client._get_tags("/tags/test")
            assert tags == [{"key": "env", "value": "production"}]

    async def test_returns_empty_list_on_error(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that an empty list is returned on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            tags = await sentry_client._get_tags("/tags/test")
            assert tags == []


class TestGetSingleResource:
    """Tests for the _get_single_resource method."""

    async def test_returns_resource_on_success(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests successful retrieval of a single resource."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"id": "123", "name": "Test Resource"}
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            resource = await sentry_client._get_single_resource("/resource/123")
            assert resource == {"id": "123", "name": "Test Resource"}

    async def test_returns_empty_dict_on_error(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that an empty dict is returned on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            resource = await sentry_client._get_single_resource("/resource/123")
            assert resource == {}


class TestGetPaginatedProjects:
    """Tests for the get_paginated_projects method."""

    async def test_yields_projects(self, sentry_client: SentryClient) -> None:
        """Tests that projects are yielded correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"slug": "project-1"}, {"slug": "project-2"}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            projects = []
            async for page in sentry_client.get_paginated_projects():
                projects.extend(page)

            assert projects == [{"slug": "project-1"}, {"slug": "project-2"}]


class TestGetPaginatedProjectSlugs:
    """Tests for the get_paginated_project_slugs method."""

    async def test_yields_project_slugs(self, sentry_client: SentryClient) -> None:
        """Tests that project slugs are yielded correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"slug": "project-1"}, {"slug": "project-2"}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            slugs = []
            async for page in sentry_client.get_paginated_project_slugs():
                slugs.extend(page)

            assert slugs == ["project-1", "project-2"]


class TestGetPaginatedIssues:
    """Tests for the get_paginated_issues method."""

    async def test_yields_issues_for_project(self, sentry_client: SentryClient) -> None:
        """Tests that issues are yielded for a specific project."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"id": "issue-1"}, {"id": "issue-2"}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            issues = []
            async for page in sentry_client.get_paginated_issues("test-project"):
                issues.extend(page)

            assert issues == [{"id": "issue-1"}, {"id": "issue-2"}]
            # Verify the correct URL was called
            mock_request.assert_awaited()
            call_args = mock_request.call_args
            assert "test-org/test-project/issues" in call_args[0][1]


class TestGetPaginatedTeams:
    """Tests for the get_paginated_teams method."""

    async def test_yields_teams(self, sentry_client: SentryClient) -> None:
        """Tests that teams are yielded correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"slug": "team-1"}, {"slug": "team-2"}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            teams = []
            async for page in sentry_client.get_paginated_teams():
                teams.extend(page)

            assert teams == [{"slug": "team-1"}, {"slug": "team-2"}]


class TestGetPaginatedUsers:
    """Tests for the get_paginated_users method."""

    async def test_yields_users(self, sentry_client: SentryClient) -> None:
        """Tests that users are yielded correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"id": "user-1"}, {"id": "user-2"}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            users = []
            async for page in sentry_client.get_paginated_users():
                users.extend(page)

            assert users == [{"id": "user-1"}, {"id": "user-2"}]


class TestGetTeamMembers:
    """Tests for the get_team_members method."""

    async def test_returns_team_members(self, sentry_client: SentryClient) -> None:
        """Tests that team members are returned correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = [{"id": "member-1"}, {"id": "member-2"}]
        mock_response.headers = httpx.Headers({})
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            members = await sentry_client.get_team_members("test-team")

            assert members == [{"id": "member-1"}, {"id": "member-2"}]
            # Verify the correct URL was called
            mock_request.assert_awaited()
            call_args = mock_request.call_args
            assert "test-org/test-team/members" in call_args[0][1]


class TestGetIssue:
    """Tests for the get_issue method."""

    async def test_returns_issue(self, sentry_client: SentryClient) -> None:
        """Tests that an issue is returned correctly."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"id": "123", "title": "Test Issue"}
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({})
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            issue = await sentry_client.get_issue("123")

            assert issue == {"id": "123", "title": "Test Issue"}
            # Verify the correct URL was called
            mock_request.assert_awaited()
            call_args = mock_request.call_args
            assert "test-org/issues/123" in call_args[0][1]

    async def test_returns_empty_dict_on_error(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that an empty dict is returned on HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = httpx.Headers({})
        error = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )
        mock_response.raise_for_status.side_effect = error

        with patch.object(
            sentry_client._client,
            "request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            issue = await sentry_client.get_issue("123")
            assert issue == {}


class TestGetIssuesTagsFromIssues:
    """Tests for the get_issues_tags_from_issues method."""

    async def test_returns_issues_with_tags(self, sentry_client: SentryClient) -> None:
        """Tests that issues with tags are returned correctly."""
        issues = [{"id": "1"}, {"id": "2"}]

        # Mock _get_issue_tags_iterator to return tags
        async def mock_get_issue_tags_iterator(
            tag: str | None, issue: dict[str, Any]
        ) -> Any:
            yield [{**issue, "__tags": [{"key": "env", "value": "prod"}]}]

        with patch.object(
            sentry_client,
            "_get_issue_tags_iterator",
            side_effect=mock_get_issue_tags_iterator,
        ):
            result = await sentry_client.get_issues_tags_from_issues(
                "environment", issues
            )

            assert len(result) == 2
            for item in result:
                assert "__tags" in item


class TestGetProjectsTagsFromProjects:
    """Tests for the get_projects_tags_from_projects method."""

    async def test_returns_projects_with_tags(
        self, sentry_client: SentryClient
    ) -> None:
        """Tests that projects with tags are returned correctly."""
        projects = [{"slug": "project-1"}, {"slug": "project-2"}]

        # Mock _get_project_tags_iterator to return tags
        async def mock_get_project_tags_iterator(
            tag: str | None, project: dict[str, Any]
        ) -> Any:
            yield [{**project, "__tags": {"key": "env", "value": "prod"}}]

        with patch.object(
            sentry_client,
            "_get_project_tags_iterator",
            side_effect=mock_get_project_tags_iterator,
        ):
            result = await sentry_client.get_projects_tags_from_projects(
                "environment", projects
            )

            assert len(result) == 2
            for item in result:
                assert "__tags" in item
