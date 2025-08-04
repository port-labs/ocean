from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, AsyncMock
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.clients.http.rest_client import GithubRestClient
from integration import GithubPullRequestSelector
from port_ocean.context.event import event_context
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from datetime import datetime, timezone, timedelta

# Calculate dates relative to current time to ensure they're within the 60-day window
now = datetime.now(timezone.utc)
recent_date = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
older_recent_date = (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
old_date = (now - timedelta(days=70)).strftime(
    "%Y-%m-%dT%H:%M:%SZ"
)  # This will be filtered out

TEST_PULL_REQUESTS = [
    {
        "id": 1,
        "number": 101,
        "title": "Fix bug in login",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/101",
        "updated_at": recent_date,
    },
    {
        "id": 2,
        "number": 102,
        "title": "Add new feature",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/102",
        "updated_at": older_recent_date,
    },
]

TEST_CLOSED_PULL_REQUESTS = [
    {
        "id": 3,
        "number": 103,
        "title": "Closed PR 1",
        "state": "closed",
        "html_url": "https://github.com/test-org/repo1/pull/103",
        "updated_at": recent_date,
    },
    {
        "id": 4,
        "number": 104,
        "title": "Closed PR 2",
        "state": "closed",
        "html_url": "https://github.com/test-org/repo1/pull/104",
        "updated_at": older_recent_date,
    },
    {
        "id": 5,
        "number": 105,
        "title": "Old Closed PR",
        "state": "closed",
        "html_url": "https://github.com/test-org/repo1/pull/105",
        "updated_at": old_date,
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

    async def test_get_paginated_resources_open_only(
        self, rest_client: GithubRestClient
    ) -> None:
        selector = GithubPullRequestSelector(
            query="true", state="open", closedPullRequests=False
        )
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

    async def test_get_paginated_resources_with_closed(
        self, rest_client: GithubRestClient
    ) -> None:
        selector = GithubPullRequestSelector(
            query="true", state="open", closedPullRequests=True
        )
        exporter = RestPullRequestExporter(rest_client)

        # Track call count to return different responses
        call_count = 0

        async def mock_paginated_request(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First call: open PRs
                yield TEST_PULL_REQUESTS
            elif call_count == 2:
                # Second call: closed PRs
                yield TEST_CLOSED_PULL_REQUESTS[:2]  # Only the recent ones

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_paginated:
            async with event_context("test_event"):
                # Convert selector to options dict
                options = ListPullRequestOptions(
                    state=selector.state, repo_name="repo1", include_closed=True
                )
                prs: list[list[dict[str, Any]]] = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

                assert len(prs) == 2  # Open PRs batch + Closed PRs batch
                assert len(prs[0]) == 2  # Open PRs
                assert len(prs[1]) == 2  # Closed PRs (filtered)

                expected_open_prs = [
                    {**pr, "__repository": "repo1"} for pr in TEST_PULL_REQUESTS
                ]
                expected_closed_prs = [
                    {**pr, "__repository": "repo1"}
                    for pr in TEST_CLOSED_PULL_REQUESTS[:2]
                ]
                assert prs[0] == expected_open_prs
                assert prs[1] == expected_closed_prs

            # Should be called twice: once for open PRs, once for closed PRs
            assert mock_paginated.call_count == 2

    async def test_fetch_open_pull_requests(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)
        params = {"state": "open"}

        async def mock_prs_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_PULL_REQUESTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_prs_request
        ) as mock_paginated:
            batches = [
                batch
                async for batch in exporter._fetch_open_pull_requests("repo1", params)
            ]

            assert len(batches) == 1
            assert len(batches[0]) == 2
            expected_prs = [
                {**pr, "__repository": "repo1"} for pr in TEST_PULL_REQUESTS
            ]
            assert batches[0] == expected_prs

            mock_paginated.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/pulls",
                {"state": "open"},
            )

    async def test_fetch_closed_pull_requests(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)

        async def mock_closed_prs_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_CLOSED_PULL_REQUESTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_closed_prs_request
        ) as mock_paginated:
            batches = [
                batch async for batch in exporter._fetch_closed_pull_requests("repo1")
            ]

            assert len(batches) == 1
            assert len(batches[0]) == 2  # Only the recent ones (filtered)
            expected_prs = [
                {**pr, "__repository": "repo1"} for pr in TEST_CLOSED_PULL_REQUESTS[:2]
            ]
            assert batches[0] == expected_prs

            mock_paginated.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/pulls",
                {"state": "closed", "sort": "updated", "direction": "desc"},
            )

    async def test_fetch_closed_pull_requests_empty_batch(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)

        async def mock_empty_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []  # Empty batch

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_empty_request
        ) as mock_paginated:
            batches = [
                batch async for batch in exporter._fetch_closed_pull_requests("repo1")
            ]

            assert len(batches) == 0  # No batches should be yielded
            mock_paginated.assert_called_once()

    async def test_fetch_closed_pull_requests_batch_limit(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)

        # Create more batches than the limit
        async def mock_multiple_batches(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            for i in range(3):  # More than the limit (100/100 = 1 batch)
                yield [{"id": i, "updated_at": recent_date}]

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_multiple_batches
        ) as mock_paginated:
            batches = [
                batch async for batch in exporter._fetch_closed_pull_requests("repo1")
            ]

            # Should only get 1 batch due to the limit
            assert len(batches) == 1
            assert mock_paginated.call_count == 1

    def test_filter_prs_by_updated_at(self, rest_client: GithubRestClient) -> None:
        exporter = RestPullRequestExporter(rest_client)

        # Create PRs with different creation dates
        recent_pr = {"id": 1, "updated_at": recent_date}
        old_pr = {"id": 2, "updated_at": old_date}

        prs = [recent_pr, old_pr]
        filtered = exporter._filter_prs_by_updated_at(prs)

        # Only the recent PR should be included
        assert len(filtered) == 1
        assert filtered[0]["id"] == 1
