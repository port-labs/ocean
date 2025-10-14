from typing import Any, AsyncGenerator, Generator
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, UTC, timedelta
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.clients.http.rest_client import GithubRestClient
from port_ocean.context.event import event_context
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions

TEST_PULL_REQUESTS = [
    {
        "id": 1,
        "number": 101,
        "title": "Fix bug in login",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/101",
        "updated_at": "2025-08-15T15:08:15Z",  # do not change this value
    },
    {
        "id": 2,
        "number": 102,
        "title": "Add new feature",
        "state": "open",
        "html_url": "https://github.com/test-org/repo1/pull/102",
        "updated_at": "2025-08-15T15:08:15Z",  # do not change this value
    },
]


@pytest.fixture
def mock_datetime() -> Generator[datetime, None, None]:
    """Fixture that mocks the datetime module for consistent testing."""
    with patch("github.core.exporters.pull_request_exporter.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(
            2025, 8, 19, 12, 0, 0, tzinfo=UTC
        )  # do not change this value
        mock_dt.UTC = UTC
        mock_dt.timedelta = timedelta
        mock_dt.strptime = datetime.strptime
        yield mock_dt


@pytest.mark.asyncio
class TestPullRequestExporter:

    async def test_get_resource(self, rest_client: GithubRestClient) -> None:
        exporter = RestPullRequestExporter(rest_client)

        with patch.object(
            rest_client,
            "send_api_request",
            AsyncMock(return_value=TEST_PULL_REQUESTS[0]),
        ) as mock_request:
            pr = await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org", repo_name="repo1", pr_number=101
                )
            )

            expected_pr = {**TEST_PULL_REQUESTS[0], "__repository": "repo1"}
            assert pr == expected_pr

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/test-org/repo1/pulls/101"
            )

    @pytest.mark.parametrize(
        "states, expected_calls",
        [
            (["open"], [{"state": "open"}]),
            (["closed"], [{"state": "closed", "sort": "updated", "direction": "desc"}]),
            (
                ["open", "closed"],
                [
                    {"state": "open"},
                    {"state": "closed", "sort": "updated", "direction": "desc"},
                ],
            ),
        ],
    )
    async def test_get_paginated_resources_various_states(
        self,
        rest_client: GithubRestClient,
        mock_datetime: datetime,
        states: list[str],
        expected_calls: list[dict[str, Any]],
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)

        async def mock_prs_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield TEST_PULL_REQUESTS

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_prs_request
        ) as mock_paginated:
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=states,
                    repo_name="repo1",
                    max_results=10,
                    since=60,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

            # Ensure enriched data
            expected_batches = [
                [{**pr, "__repository": "repo1"} for pr in TEST_PULL_REQUESTS]
                for _ in expected_calls
            ]
            assert results == expected_batches

            # Check call params match expected for each branch
            actual_calls = [
                (call.args[0], call.args[1]) for call in mock_paginated.call_args_list
            ]
            expected_call_args = [
                (
                    f"{rest_client.base_url}/repos/test-org/repo1/pulls",
                    params,
                )
                for params in expected_calls
            ]
            assert actual_calls == expected_call_args

    async def test_get_paginated_resources_respects_max_results(
        self, rest_client: GithubRestClient, mock_datetime: datetime
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)

        many_prs = [
            {**TEST_PULL_REQUESTS[0], "id": i, "number": 100 + i} for i in range(1, 11)
        ]

        async def mock_closed_prs_request_single_batch(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield many_prs  # One big batch

        async def mock_closed_prs_request_multiple_batches(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield many_prs[:3]  # Batch 1: 3 PRs
            yield many_prs[
                3:7
            ]  # Batch 2: 4 PRs → should trim to only 2 PRs to reach max=5
            yield many_prs[7:]  # Would be ignored entirely

        # --- Case 1: single large batch ---
        with patch.object(
            rest_client,
            "send_paginated_request",
            side_effect=mock_closed_prs_request_single_batch,
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=5,
                    since=60,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 5
        assert flat_results == [{**pr, "__repository": "repo1"} for pr in many_prs[:5]]

        # --- Case 2: multiple batches ---
        with patch.object(
            rest_client,
            "send_paginated_request",
            side_effect=mock_closed_prs_request_multiple_batches,
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=5,
                    since=60,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 5
        # Should be first 3 from batch1 + first 2 from batch2
        expected_prs = many_prs[:3] + many_prs[3:5]
        assert flat_results == [{**pr, "__repository": "repo1"} for pr in expected_prs]

    async def test_since_parameter_filters_closed_prs(
        self, rest_client: GithubRestClient, mock_datetime: datetime
    ) -> None:
        """Test that the since parameter correctly filters closed PRs and interacts with max_results."""
        exporter = RestPullRequestExporter(rest_client)

        # Test data with mixed timestamps - some recent, some old
        test_prs = [
            {
                "id": 1,
                "number": 101,
                "title": "Recent PR 1",
                "state": "closed",
                "html_url": "https://github.com/test-org/repo1/pull/101",
                "updated_at": "2025-08-10T15:08:15Z",  # Most recent (within 30 days)
            },
            {
                "id": 3,
                "number": 103,
                "title": "Recent PR 2",
                "state": "closed",
                "html_url": "https://github.com/test-org/repo1/pull/103",
                "updated_at": "2025-08-05T15:08:15Z",  # Second most recent (within 30 days)
            },
            {
                "id": 4,
                "number": 104,
                "title": "Recent PR 3",
                "state": "closed",
                "html_url": "https://github.com/test-org/repo1/pull/104",
                "updated_at": "2025-08-01T15:08:15Z",  # Third most recent (within 30 days)
            },
            {
                "id": 5,
                "number": 105,
                "title": "Recent PR 4",
                "state": "closed",
                "html_url": "https://github.com/test-org/repo1/pull/105",
                "updated_at": "2025-07-28T15:08:15Z",  # Fourth most recent (within 30 days)
            },
            {
                "id": 6,
                "number": 106,
                "title": "Recent PR 5",
                "state": "closed",
                "html_url": "https://github.com/test-org/repo1/pull/106",
                "updated_at": "2025-07-25T15:08:15Z",  # Fifth most recent (within 30 days)
            },
            {
                "id": 2,
                "number": 102,
                "title": "Old PR 1",
                "state": "closed",
                "html_url": "https://github.com/test-org/repo1/pull/102",
                "updated_at": "2025-01-15T15:08:15Z",  # Old (outside 90 days)
            },
        ]

        # Test the integration flow where both max_results and since work together
        async def mock_closed_prs_request(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield test_prs

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_closed_prs_request
        ):
            async with event_context("test_event"):
                # Test 1: since=30 days with max_results=10 (should get only 5 PRs due to since filtering)
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=10,
                    since=30,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        # Should only return 2 PRs (limited by since=30), even though max_results=10 would allow more
        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 5  # Limited by since=30, not by max_results
        assert flat_results[0]["id"] == 1  # Recent PR 1
        assert flat_results[1]["id"] == 3  # Recent PR 2

        # Test 2: since=30 days with max_results=3 (should get only 3 PRs due to max_results limiting)
        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_closed_prs_request
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=3,
                    since=90,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        # Should only return 3 PRs (limited by max_results=3), even though since=30 allows 6 recent PRs
        flat_results = [pr for batch in results for pr in batch]
        assert (
            len(flat_results) == 3
        )  # Limited by max_results=3, not by since filtering
        assert flat_results[0]["id"] == 1  # First recent PR
        assert flat_results[1]["id"] == 3  # Second recent PR
        assert flat_results[2]["id"] == 4  # Third recent PR
