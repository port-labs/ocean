from typing import Any, AsyncGenerator, Generator
import pytest
from unittest.mock import patch, AsyncMock
from datetime import datetime, UTC, timedelta
from github.core.exporters.pull_request_exporter import (
    RestPullRequestExporter,
    GraphQLPullRequestExporter,
)
from github.clients.http.rest_client import GithubRestClient
from github.clients.http.graphql_client import GithubGraphQLClient
from port_ocean.context.event import event_context
from github.core.options import (
    SinglePullRequestOptions,
    ListPullRequestOptions,
    PullRequestGraphQLOptions,
)
from github.helpers.gql_queries import (
    generate_list_pull_requests_gql,
    generate_pull_request_details_gql,
)
from github.core.exporters.pull_request_exporter.utils import filter_prs_by_date
from integration import GithubPullRequestSelector


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
    with patch("github.core.exporters.pull_request_exporter.utils.datetime") as mock_dt:
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

            expected_pr = {
                **TEST_PULL_REQUESTS[0],
                "__repository": "repo1",
                "__organization": "test-org",
            }
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
        mock_datetime: Any,
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
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=60),
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

            # Ensure enriched data
            expected_batches = [
                [
                    {**pr, "__repository": "repo1", "__organization": "test-org"}
                    for pr in TEST_PULL_REQUESTS
                ]
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
        self, rest_client: GithubRestClient, mock_datetime: Any
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
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=60),
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 5
        assert flat_results == [
            {**pr, "__repository": "repo1", "__organization": "test-org"}
            for pr in many_prs[:5]
        ]

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
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=60),
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 5
        # Should be first 3 from batch1 + first 2 from batch2
        expected_prs = many_prs[:3] + many_prs[3:5]
        assert flat_results == [
            {**pr, "__repository": "repo1", "__organization": "test-org"}
            for pr in expected_prs
        ]

    async def test_since_parameter_filters_closed_prs(
        self, rest_client: GithubRestClient, mock_datetime: Any
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
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=30),
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
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=90),
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

    async def test_unbounded_when_max_results_none(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)
        updated_after = datetime(2025, 1, 1, tzinfo=UTC)
        page1 = [
            {
                "id": i,
                "number": i,
                "updated_at": "2025-08-15T15:08:15Z",
                "closed_at": "2025-08-15T15:08:15Z",
            }
            for i in range(60)
        ]
        page2 = [
            {
                "id": 100 + i,
                "number": 100 + i,
                "updated_at": "2025-08-15T15:08:15Z",
                "closed_at": "2025-08-15T15:08:15Z",
            }
            for i in range(60)
        ]

        async def mock_closed(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield page1
            yield page2

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_closed
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=None,
                    updated_after=updated_after,
                    use_close_date=True,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 120

    async def test_date_driven_early_exit_stops_pagination(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)
        updated_after = datetime(2025, 6, 1, tzinfo=UTC)
        page1 = [
            {
                "id": 1,
                "number": 1,
                "updated_at": "2025-08-10T00:00:00Z",
                "closed_at": "2025-08-10T00:00:00Z",
            },
            {
                "id": 2,
                "number": 2,
                "updated_at": "2025-08-05T00:00:00Z",
                "closed_at": "2025-08-05T00:00:00Z",
            },
            {
                "id": 3,
                "number": 3,
                "updated_at": "2025-08-01T00:00:00Z",
                "closed_at": "2025-08-01T00:00:00Z",
            },
        ]
        page2 = [
            {
                "id": 4,
                "number": 4,
                "updated_at": "2025-07-01T00:00:00Z",
                "closed_at": "2025-07-01T00:00:00Z",
            },
            {
                "id": 5,
                "number": 5,
                "updated_at": "2025-05-15T00:00:00Z",
                "closed_at": "2025-05-15T00:00:00Z",
            },
            {
                "id": 6,
                "number": 6,
                "updated_at": "2025-05-01T00:00:00Z",
                "closed_at": "2025-05-01T00:00:00Z",
            },
        ]
        page3 = [
            {
                "id": 7,
                "number": 7,
                "updated_at": "2025-09-01T00:00:00Z",
                "closed_at": "2025-09-01T00:00:00Z",
            },
        ]

        async def mock_closed(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield page1
            yield page2
            yield page3

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_closed
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=None,
                    updated_after=updated_after,
                    use_close_date=True,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        ids = [pr["id"] for batch in results for pr in batch]
        assert ids == [1, 2, 3, 4]

    async def test_since_date_selector_fetches_all_closed_until_now(
        self, rest_client: GithubRestClient
    ) -> None:
        selector = GithubPullRequestSelector.parse_obj(
            {"query": "true", "states": ["closed"], "sinceDate": "2025-01-01"}
        )
        assert selector.effective_max_results is None
        assert selector.updated_after == datetime(2025, 1, 1, tzinfo=UTC)

        exporter = RestPullRequestExporter(rest_client)
        page1 = [
            {
                "id": 1,
                "number": 1,
                "updated_at": "2025-03-01T00:00:00Z",
                "closed_at": "2025-03-01T00:00:00Z",
            },
            {
                "id": 2,
                "number": 2,
                "updated_at": "2025-02-01T00:00:00Z",
                "closed_at": "2024-11-01T00:00:00Z",
            },
        ]
        page2 = [
            {
                "id": 3,
                "number": 3,
                "updated_at": "2025-01-05T00:00:00Z",
                "closed_at": "2025-01-05T00:00:00Z",
            },
            {
                "id": 4,
                "number": 4,
                "updated_at": "2024-12-20T00:00:00Z",
                "closed_at": "2024-12-20T00:00:00Z",
            },
        ]
        page3 = [
            {
                "id": 5,
                "number": 5,
                "updated_at": "2025-06-01T00:00:00Z",
                "closed_at": "2025-06-01T00:00:00Z",
            },
        ]

        async def mock_closed(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield page1
            yield page2
            yield page3

        with patch.object(
            rest_client, "send_paginated_request", side_effect=mock_closed
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=list(selector.states),
                    repo_name="repo1",
                    max_results=selector.effective_max_results,
                    updated_after=selector.updated_after,
                    use_close_date=selector.since_date is not None,
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        ids = [pr["id"] for batch in results for pr in batch]
        assert ids == [1, 3]


@pytest.mark.asyncio
class TestGraphQLPullRequestExporter:
    async def test_get_resource(self, graphql_client: GithubGraphQLClient) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        mock_pr_node = {
            "id": 1,
            "number": 101,
            "title": "GraphQL PR",
            "state": "OPEN",
            "assignees": {"nodes": []},
            "reviewRequests": {"nodes": []},
            "comments": {"totalCount": 2},
            "reviewThreads": {"totalCount": 1},
            "commits": {"totalCount": 3},
            "labels": {"nodes": []},
            "mergeStateStatus": "CLEAN",
            "mergeable": "MERGEABLE",
        }
        mock_response = {
            "data": {"repository": {"pullRequest": mock_pr_node}},
        }

        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.parse_github_options",
                return_value=(
                    "repo1",
                    "test-org",
                    {"pr_number": 101, "repo": {"name": "repo1"}},
                ),
            ) as mock_parse,
            patch.object(
                graphql_client,
                "send_api_request",
                return_value=mock_response,
            ) as mock_request,
        ):
            pr = await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=101,
                )
            )

        expected_variables = {
            "organization": "test-org",
            "repo": "repo1",
            "prNumber": 101,
        }
        expected_payload = graphql_client.build_graphql_payload(
            query=generate_pull_request_details_gql(
                PullRequestGraphQLOptions(enrich_with_first_commit=False)
            ),
            variables=expected_variables,
        )

        mock_parse.assert_called_once()
        mock_request.assert_called_once_with(
            graphql_client.base_url,
            method="POST",
            json_data=expected_payload,
        )

        # Normalization assertions
        assert pr is not None
        assert pr["__organization"] == "test-org"
        assert pr["__repository"] == "repo1"
        assert pr["comments"] == 2
        assert pr["review_comments"] == 1
        assert pr["commits"] == 3
        assert pr["state"] == "open"
        assert "firstCommit" not in pr

    async def test_get_resource_respects_exclude_graphql_fields(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        mock_pr_node = {
            "id": 1,
            "number": 101,
            "title": "GraphQL PR",
        }
        mock_response = {"data": {"repository": {"pullRequest": mock_pr_node}}}

        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.parse_github_options",
                return_value=(
                    "repo1",
                    "test-org",
                    {
                        "pr_number": 101,
                        "repo": {"name": "repo1"},
                        "exclude_graphql_fields": [
                            "additions",
                            "deletions",
                            "changedFiles",
                        ],
                    },
                ),
            ),
            patch.object(
                graphql_client,
                "send_api_request",
                return_value=mock_response,
            ) as mock_request,
        ):
            await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=101,
                )
            )

        expected_payload = graphql_client.build_graphql_payload(
            query=generate_pull_request_details_gql(
                PullRequestGraphQLOptions(
                    enrich_with_first_commit=False,
                    exclude_graphql_fields=["additions", "deletions", "changedFiles"],
                )
            ),
            variables={"organization": "test-org", "repo": "repo1", "prNumber": 101},
        )
        mock_request.assert_called_once_with(
            graphql_client.base_url,
            method="POST",
            json_data=expected_payload,
        )

    async def test_get_resource_enrich_with_first_commit(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        mock_pr_node = {
            "id": 1,
            "number": 101,
            "title": "GraphQL PR",
            "state": "OPEN",
            "assignees": {"nodes": []},
            "reviewRequests": {"nodes": []},
            "comments": {"totalCount": 2},
            "reviewThreads": {"totalCount": 1},
            "commits": {
                "totalCount": 3,
                "nodes": [
                    {
                        "commit": {
                            "oid": "abc123def",
                            "committedDate": "2025-01-15T10:00:00Z",
                        }
                    }
                ],
            },
            "labels": {"nodes": []},
            "mergeStateStatus": "CLEAN",
            "mergeable": "MERGEABLE",
        }
        mock_response = {
            "data": {"repository": {"pullRequest": mock_pr_node}},
        }

        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.parse_github_options",
                return_value=(
                    "repo1",
                    "test-org",
                    {
                        "pr_number": 101,
                        "repo": {"name": "repo1"},
                        "enrich_with_first_commit": True,
                    },
                ),
            ),
            patch.object(
                graphql_client,
                "send_api_request",
                return_value=mock_response,
            ) as mock_request,
        ):
            pr = await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=101,
                    repo={"name": "repo1"},
                    enrich_with_first_commit=True,
                )
            )

        expected_payload = graphql_client.build_graphql_payload(
            query=generate_pull_request_details_gql(
                PullRequestGraphQLOptions(enrich_with_first_commit=True)
            ),
            variables={
                "organization": "test-org",
                "repo": "repo1",
                "prNumber": 101,
            },
        )
        mock_request.assert_called_once_with(
            graphql_client.base_url,
            method="POST",
            json_data=expected_payload,
        )
        assert pr is not None
        assert pr["firstCommit"]["oid"] == "abc123def"
        assert pr["firstCommit"]["committedDate"] == "2025-01-15T10:00:00Z"

    async def test_get_paginated_resources_open_and_closed(
        self, graphql_client: GithubGraphQLClient, mock_datetime: Any
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        open_nodes = [
            {
                "id": 1,
                "number": 11,
                "title": "Open PR",
                "state": "OPEN",
                "assignees": {"nodes": []},
                "reviewRequests": {"nodes": []},
                "comments": {"totalCount": 0},
                "reviewThreads": {"totalCount": 0},
                "commits": {"totalCount": 1},
                "labels": {"nodes": []},
                "mergeStateStatus": "CLEAN",
                "mergeable": "MERGEABLE",
            }
        ]
        closed_nodes = [
            {
                "id": 2,
                "number": 12,
                "title": "Closed PR",
                "state": "CLOSED",
                "assignees": {"nodes": []},
                "reviewRequests": {"nodes": []},
                "comments": {"totalCount": 1},
                "reviewThreads": {"totalCount": 0},
                "commits": {"totalCount": 2},
                "updatedAt": "2025-08-10T15:08:15Z",
                "labels": {"nodes": []},
                "mergeStateStatus": "CLEAN",
                "mergeable": "MERGEABLE",
            }
        ]

        async def mock_open(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield open_nodes

        async def mock_closed(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield closed_nodes

        with (
            patch.object(
                graphql_client,
                "send_paginated_request",
                side_effect=[mock_open(), mock_closed()],
            ) as mock_paginated,
            patch(
                "github.core.exporters.pull_request_exporter.core.filter_prs_by_date",
                side_effect=lambda prs, field, since: prs,
            ),
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["open", "closed"],
                    repo_name="repo1",
                    max_results=10,
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=30),
                    repo={"name": "repo1"},
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        # We expect two batches: one for open and one for closed PRs
        assert len(batches) == 2
        assert len(batches[0]) == 1
        assert len(batches[1]) == 1

        # Ensure GraphQL variables were built correctly for both calls
        mock_paginated.assert_any_call(
            generate_list_pull_requests_gql(
                PullRequestGraphQLOptions(enrich_with_first_commit=False)
            ),
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["OPEN"],
                "__path": "repository.pullRequests",
            },
        )
        mock_paginated.assert_any_call(
            generate_list_pull_requests_gql(
                PullRequestGraphQLOptions(enrich_with_first_commit=False)
            ),
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["CLOSED", "MERGED"],
                "__path": "repository.pullRequests",
            },
        )

    async def test_get_paginated_resources_passes_enriched_query_when_enabled(
        self, graphql_client: GithubGraphQLClient, mock_datetime: Any
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        async def mock_open(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [
                {
                    "id": 1,
                    "number": 11,
                    "title": "Open PR",
                    "state": "OPEN",
                    "assignees": {"nodes": []},
                    "reviewRequests": {"nodes": []},
                    "comments": {"totalCount": 0},
                    "reviewThreads": {"totalCount": 0},
                    "commits": {
                        "totalCount": 1,
                        "nodes": [
                            {
                                "commit": {
                                    "oid": "sha1",
                                    "committedDate": "2025-02-01T00:00:00Z",
                                }
                            }
                        ],
                    },
                    "labels": {"nodes": []},
                    "mergeStateStatus": "CLEAN",
                    "mergeable": "MERGEABLE",
                }
            ]

        with patch.object(
            graphql_client,
            "send_paginated_request",
            side_effect=[mock_open()],
        ) as mock_paginated:
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["open"],
                    repo_name="repo1",
                    max_results=10,
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=30),
                    repo={"name": "repo1"},
                    enrich_with_first_commit=True,
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        assert len(batches) == 1
        assert batches[0][0]["firstCommit"]["oid"] == "sha1"
        mock_paginated.assert_called_once_with(
            generate_list_pull_requests_gql(
                PullRequestGraphQLOptions(enrich_with_first_commit=True)
            ),
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["OPEN"],
                "__path": "repository.pullRequests",
            },
        )

    async def test_closed_prs_use_closed_at_filter_and_max_results(
        self, graphql_client: GithubGraphQLClient, mock_datetime: Any
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        pr_nodes = [
            {
                "id": 1,
                "closedAt": "2025-08-10T15:08:15Z",
                "updatedAt": "2025-08-10T15:08:15Z",
            },
            {
                "id": 2,
                "closedAt": "2025-08-05T15:08:15Z",
                "updatedAt": "2025-08-05T15:08:15Z",
            },
            {
                "id": 3,
                "closedAt": "2025-07-01T15:08:15Z",
                "updatedAt": "2025-07-01T15:08:15Z",
            },
        ]

        async def mock_closed(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield pr_nodes

        with (
            patch.object(
                graphql_client,
                "send_paginated_request",
                side_effect=mock_closed,
            ) as mock_paginated,
            patch(
                "github.core.exporters.pull_request_exporter.core.filter_prs_by_date",
                side_effect=lambda prs, field, updated_after: prs[:2],
            ) as mock_filter,
            patch.object(
                GraphQLPullRequestExporter,
                "_normalize_pr_node",
                side_effect=lambda pr, repo, org, **kwargs: {
                    **pr,
                    "__repository": repo,
                    "__organization": org,
                },
            ) as mock_normalize,
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=2,
                    updated_after=mock_datetime.now(mock_datetime.UTC)
                    - mock_datetime.timedelta(days=30),
                    use_close_date=True,
                    repo={"name": "repo1"},
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        # Only one batch, limited by max_results and filter output
        assert len(batches) == 1
        assert len(batches[0]) == 2

        assert mock_filter.call_count == 2
        # Inclusion filters on closedAt; the stop check filters on updatedAt
        fields = [call.args[1] for call in mock_filter.call_args_list]
        assert fields == ["closedAt", "updatedAt"]

        mock_paginated.assert_called_once_with(
            generate_list_pull_requests_gql(
                PullRequestGraphQLOptions(enrich_with_first_commit=False),
                order_by_field="UPDATED_AT",
            ),
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["CLOSED", "MERGED"],
                "__path": "repository.pullRequests",
            },
        )
        assert mock_normalize.call_count == 2

    async def test_date_driven_early_exit_stops_pagination(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)
        updated_after = datetime(2025, 6, 1, tzinfo=UTC)
        page1 = [
            {
                "id": 1,
                "closedAt": "2025-08-10T00:00:00Z",
                "updatedAt": "2025-08-10T00:00:00Z",
            },
            {
                "id": 2,
                "closedAt": "2025-08-01T00:00:00Z",
                "updatedAt": "2025-08-01T00:00:00Z",
            },
        ]
        page2 = [
            {
                "id": 3,
                "closedAt": "2025-07-01T00:00:00Z",
                "updatedAt": "2025-07-01T00:00:00Z",
            },
            {
                "id": 4,
                "closedAt": "2025-05-01T00:00:00Z",
                "updatedAt": "2025-05-01T00:00:00Z",
            },
        ]
        page3 = [
            {
                "id": 5,
                "closedAt": "2025-09-01T00:00:00Z",
                "updatedAt": "2025-09-01T00:00:00Z",
            },
        ]

        async def mock_closed(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield page1
            yield page2
            yield page3

        with (
            patch.object(
                graphql_client, "send_paginated_request", side_effect=mock_closed
            ),
            patch.object(
                GraphQLPullRequestExporter,
                "_normalize_pr_node",
                side_effect=lambda pr, repo, org, **kwargs: pr,
            ),
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["closed"],
                    repo_name="repo1",
                    max_results=None,
                    updated_after=updated_after,
                    use_close_date=True,
                    repo={"name": "repo1"},
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        ids = [pr["id"] for batch in batches for pr in batch]
        assert ids == [1, 2, 3]


class TestGraphQLPullRequestExporterInternals:
    def test_normalize_pr_node_enriches_and_flattens(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        pr_node = {
            "id": "PR_kw",
            "state": "OPEN",
            "assignees": {"nodes": [{"login": "assignee"}]},
            "reviewRequests": {"nodes": []},
            "comments": {"totalCount": 5},
            "reviewThreads": {"totalCount": 2},
            "commits": {
                "totalCount": 3,
                "nodes": [
                    {
                        "commit": {
                            "oid": "firstsha",
                            "committedDate": "2025-03-01T08:30:00Z",
                        }
                    }
                ],
            },
            "labels": {"nodes": []},
            "mergeStateStatus": "CLEAN",
            "mergeable": "MERGEABLE",
        }

        repo = {"name": "repo1"}
        normalized = exporter._normalize_pr_node(
            pr_node,
            repo,
            "test-org",
            gql_options=PullRequestGraphQLOptions(enrich_with_first_commit=True),
        )

        assert normalized["assignees"] == [{"login": "assignee"}]
        assert normalized["requested_reviewers"] == []
        assert normalized["comments"] == 5
        assert normalized["review_comments"] == 2
        assert normalized["commits"] == 3
        assert normalized["firstCommit"]["oid"] == "firstsha"
        assert normalized["firstCommit"]["committedDate"] == "2025-03-01T08:30:00Z"
        assert normalized["state"] == "open"
        assert normalized["__repository"] == "repo1"
        assert normalized["__organization"] == "test-org"

    def test_normalize_pr_node_skips_first_commit_fields_when_disabled(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)
        pr_node = {
            "id": "PR_kw",
            "state": "OPEN",
            "assignees": {"nodes": []},
            "reviewRequests": {"nodes": []},
            "comments": {"totalCount": 1},
            "reviewThreads": {"totalCount": 0},
            "commits": {
                "totalCount": 2,
                "nodes": [
                    {
                        "commit": {
                            "oid": "should_not_appear",
                            "committedDate": "2025-01-01T00:00:00Z",
                        }
                    }
                ],
            },
            "labels": {"nodes": []},
            "mergeStateStatus": "CLEAN",
            "mergeable": "MERGEABLE",
        }
        normalized = exporter._normalize_pr_node(
            pr_node,
            {"name": "repo1"},
            "org",
            gql_options=PullRequestGraphQLOptions(),
        )
        assert normalized["commits"] == 2
        assert "firstCommit" not in normalized

    def test_normalize_pr_node_no_commits(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        pr_node = {
            "id": "PR_empty",
            "state": "OPEN",
            "assignees": {"nodes": []},
            "reviewRequests": {"nodes": []},
            "comments": {"totalCount": 0},
            "reviewThreads": {"totalCount": 0},
            "commits": {"totalCount": 0, "nodes": []},
            "labels": {"nodes": []},
            "mergeStateStatus": "CLEAN",
            "mergeable": "MERGEABLE",
        }

        enriched = exporter._normalize_pr_node(
            pr_node,
            {"name": "r"},
            "org",
            gql_options=PullRequestGraphQLOptions(enrich_with_first_commit=True),
        )
        assert enriched["commits"] == 0
        assert "firstCommit" not in enriched

        minimal = exporter._normalize_pr_node(
            pr_node,
            {"name": "r"},
            "org",
            gql_options=PullRequestGraphQLOptions(),
        )
        assert minimal["commits"] == 0
        assert "first_commit_oid" not in minimal
        assert "first_commit_committed_at" not in minimal

    def test_extract_requested_reviewers_handles_users_and_teams(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        pr_node = {
            "reviewRequests": {
                "nodes": [
                    {
                        "requestedReviewer": {
                            "__typename": "User",
                            "login": "user1",
                        }
                    },
                    {
                        "requestedReviewer": {
                            "__typename": "Team",
                            "name": "team-name",
                            "slug": "team-slug",
                        }
                    },
                ]
            }
        }

        reviewers = exporter._extract_requested_reviewers(pr_node)

        assert reviewers == [
            {"login": "user1", "type": "User"},
            {"name": "team-name", "slug": "team-slug", "type": "Team"},
        ]

    def test_normalize_pr_node_handles_missing_fields(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)
        pr_node: dict[str, Any] = {"id": "PR_min", "title": "t", "number": 1}

        normalized = exporter._normalize_pr_node(pr_node, {"name": "repo1"}, "org")

        # Minimal nodes should not be expanded with missing fields.
        assert "assignees" not in normalized
        assert "reviewRequests" not in normalized
        assert "labels" not in normalized
        assert "requested_reviewers" not in normalized
        assert "comments" not in normalized
        assert "review_comments" not in normalized
        assert "commits" not in normalized
        assert "state" not in normalized
        assert "mergeable_state" not in normalized
        assert "mergeable" not in normalized

        # But normalization should always enrich with repo/org context.
        assert normalized["__repository"] == "repo1"
        assert normalized["__repository_object"] == {"name": "repo1"}
        assert normalized["__organization"] == "org"


def test_filter_prs_by_date_skips_items_missing_field() -> None:
    prs: list[dict[str, Any]] = [
        {"id": 1, "closedAt": "2025-08-10T15:08:15Z"},
        {"id": 2},  # missing closedAt should be ignored
    ]
    filtered = filter_prs_by_date(
        prs, "closedAt", datetime(2025, 8, 1, 0, 0, 0, tzinfo=UTC)
    )
    assert [pr["id"] for pr in filtered] == [1]


def test_pull_request_selector_accepts_exclude_graphql_fields_alias() -> None:
    selector = GithubPullRequestSelector.parse_obj(
        {
            "query": "true",
            "api": "graphql",
            "excludeGraphqlFields": ["additions", "author", "somethingElse"],
        }
    )

    assert selector.exclude_graphql_fields == ["additions", "author", "somethingElse"]


def test_pull_request_selector_since_date_overrides_since_days() -> None:
    selector = GithubPullRequestSelector.parse_obj(
        {"query": "true", "sinceDate": "2025-01-01"}
    )
    assert selector.updated_after == datetime(2025, 1, 1, tzinfo=UTC)


def test_pull_request_selector_since_date_preserves_timezone() -> None:
    selector = GithubPullRequestSelector.parse_obj(
        {"query": "true", "sinceDate": "2025-01-01T00:00:00+02:00"}
    )
    assert selector.updated_after.utcoffset() == timedelta(hours=2)


def test_pull_request_selector_updated_after_falls_back_to_since_days() -> None:
    selector = GithubPullRequestSelector.parse_obj({"query": "true", "since": 10})
    delta = datetime.now(UTC) - selector.updated_after
    assert timedelta(days=9, hours=23) < delta < timedelta(days=10, minutes=1)


def test_pull_request_selector_effective_max_results() -> None:
    days = GithubPullRequestSelector.parse_obj({"query": "true"})
    assert days.effective_max_results == 100

    since_date = GithubPullRequestSelector.parse_obj(
        {"query": "true", "sinceDate": "2025-01-01"}
    )
    assert since_date.effective_max_results is None

    explicit_with_date = GithubPullRequestSelector.parse_obj(
        {"query": "true", "sinceDate": "2025-01-01", "maxResults": 50}
    )
    assert explicit_with_date.effective_max_results == 50

    explicit_with_days = GithubPullRequestSelector.parse_obj(
        {"query": "true", "maxResults": 25}
    )
    assert explicit_with_days.effective_max_results == 25


def test_list_pull_requests_query_order_by_field() -> None:
    default_query = generate_list_pull_requests_gql(PullRequestGraphQLOptions())
    assert "field: CREATED_AT" in default_query
    assert "UPDATED_AT" not in default_query

    closed_query = generate_list_pull_requests_gql(
        PullRequestGraphQLOptions(), order_by_field="UPDATED_AT"
    )
    assert "field: UPDATED_AT" in closed_query
    assert "CREATED_AT" not in closed_query
