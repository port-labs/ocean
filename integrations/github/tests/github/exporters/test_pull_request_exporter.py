from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, AsyncMock
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPullRequestSelector
from port_ocean.context.event import event_context
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from datetime import datetime, timezone

TEST_PULL_REQUESTS = [
    {
        "id": 1,
        "number": 101,
        "title": "Fix bug in login",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/101",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": 2,
        "number": 102,
        "title": "Add new feature",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/102",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    },
]

TEST_REPOS = [
    {"id": 1, "name": "repo1", "full_name": "test-org/repo1"},
    {"id": 2, "name": "repo2", "full_name": "test-org/repo2"},
]


@pytest.mark.asyncio
class TestPullRequestExporter:

    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestPullRequestExporter(rest_client)

        with patch.object(
            rest_client,
            "send_api_request",
            AsyncMock(return_value=TEST_PULL_REQUESTS[0]),
        ) as mock_request:
            # Test with options containing repo_name and pr_number
            pr = await exporter.get_resource(
                SinglePullRequestOptions(repo_name="repo1", pr_number=101)
            )

            expected_pr = {**TEST_PULL_REQUESTS[0], "__repository": "repo1"}
            assert pr == expected_pr

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/pulls/101"
            )

    async def test_get_paginated_resources(self, rest_client: GithubRestClient) -> None:
        selector = GithubPullRequestSelector(query="true", state="open")
        exporter = RestPullRequestExporter(rest_client)

        # Create async mocks for the nested requests
        async def mock_repos_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_REPOS

        async def mock_prs_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_PULL_REQUESTS

        with patch.object(rest_client, "send_paginated_request") as mock_paginated:
            # Configure the mock to return different responses based on the endpoint
            mock_paginated.side_effect = lambda endpoint, *args, **kwargs: (
                mock_repos_request()
                if "repos" in endpoint and "pulls" not in endpoint
                else mock_prs_request()
            )

            async with event_context("test_event"):
                # Convert selector to options dict
                options = ListPullRequestOptions(
                    state=selector.state, repo_name="repo1"
                )
                prs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(prs) == 1
                assert len(prs[0]) == 2
                expected_prs = [
                    {**pr, "__repository": "repo1"} for pr in TEST_PULL_REQUESTS
                ]
                assert prs[0] == expected_prs

            mock_paginated.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/pulls",
                {"state": "open"},
            )
