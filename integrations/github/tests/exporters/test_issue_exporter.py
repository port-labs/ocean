from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, AsyncMock
from github.core.exporters.issue_exporter import RestIssueExporter
from github.clients.http.rest_client import GithubRestClient
from github.core.options import SingleIssueOptions, ListIssueOptions

TEST_ISSUES = [
    {
        "id": 1,
        "number": 101,
        "title": "Fix login bug",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/issues/101",
    },
    {
        "id": 2,
        "number": 102,
        "title": "Add new feature",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/issues/102",
    },
]

TEST_REPOS = [
    {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
    {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
]


@pytest.mark.asyncio
class TestIssueExporter:
    async def test_get_resource(self, rest_client: GithubRestClient) -> None:

        exporter = RestIssueExporter(rest_client)

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=TEST_ISSUES[0])
        ) as mock_request:
            # Test with options
            issue = await exporter.get_resource(
                SingleIssueOptions(repo_name="repo1", issue_number=101)
            )

            assert issue == {**TEST_ISSUES[0], "__repository": "repo1"}

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/issues/101"
            )

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        exporter = RestIssueExporter(rest_client)

        # Mock paginated response
        async def mock_issues_generator(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ISSUES

        with patch.object(
            rest_client, "send_paginated_request", return_value=mock_issues_generator()
        ) as mock_paginated:
            issues = []
            async for batch in exporter.get_paginated_resources(
                ListIssueOptions(repo_name="repo1", state="open")
            ):
                issues.extend(batch)

            # Assert we received all issues with repository added
            assert len(issues) == 2
            assert all(issue["__repository"] == "repo1" for issue in issues)

            # Verify specific values
            expected_issues = [
                {**issue, "__repository": "repo1"} for issue in TEST_ISSUES
            ]
            assert issues == expected_issues

            # Verify the API was called correctly
            mock_paginated.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/issues",
                {"state": "open"},
            )

    async def test_get_paginated_resources_with_different_state(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestIssueExporter(rest_client)

        # Mock paginated response
        async def mock_issues_generator(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_ISSUES

        with patch.object(
            rest_client, "send_paginated_request", return_value=mock_issues_generator()
        ) as mock_paginated:
            issues = []
            async for batch in exporter.get_paginated_resources(
                ListIssueOptions(repo_name="repo1", state="closed")
            ):
                issues.extend(batch)

            # Verify closed state was passed in parameters
            mock_paginated.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/issues",
                {"state": "closed"},
            )
