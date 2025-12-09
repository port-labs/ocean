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
from github.core.options import SinglePullRequestOptions, ListPullRequestOptions
from github.helpers.gql_queries import LIST_PULL_REQUESTS_GQL, PULL_REQUEST_DETAILS_GQL

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
                    since=60,
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
        }
        mock_response = {
            "data": {"repository": {"pullRequest": mock_pr_node}},
        }

        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.parse_github_options",
                return_value=("repo1", "test-org", {"pr_number": 101}),
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
            query=PULL_REQUEST_DETAILS_GQL,
            variables=expected_variables,
        )

        mock_parse.assert_called_once()
        mock_request.assert_called_once_with(
            graphql_client.base_url,
            method="POST",
            json_data=expected_payload,
        )

        # Normalization assertions
        assert pr["__organization"] == "test-org"
        assert pr["__repository"] == "repo1"
        assert pr["comments"] == 2
        assert pr["review_comments"] == 1
        assert pr["commits"] == 3
        assert pr["state"] == "open"

    async def test_get_paginated_resources_open_and_closed(
        self, graphql_client: GithubGraphQLClient
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
                "github.core.exporters.pull_request_exporter.core.filter_prs_by_updated_at",
                side_effect=lambda prs, field, since: prs,
            ),
        ):
            async with event_context("test_event"):
                options = ListPullRequestOptions(
                    organization="test-org",
                    states=["open", "closed"],
                    repo_name="repo1",
                    max_results=10,
                    since=30,
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
            LIST_PULL_REQUESTS_GQL,
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["OPEN"],
                "__path": "repository.pullRequests",
            },
        )
        mock_paginated.assert_any_call(
            LIST_PULL_REQUESTS_GQL,
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["CLOSED"],
                "__path": "repository.pullRequests",
            },
        )

    async def test_closed_prs_use_updated_at_filter_and_max_results(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        pr_nodes = [
            {"id": 1, "updatedAt": "2025-08-10T15:08:15Z"},
            {"id": 2, "updatedAt": "2025-08-05T15:08:15Z"},
            {"id": 3, "updatedAt": "2025-07-01T15:08:15Z"},
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
                "github.core.exporters.pull_request_exporter.core.filter_prs_by_updated_at",
                side_effect=lambda prs, field, since: prs[:2],
            ) as mock_filter,
            patch.object(
                GraphQLPullRequestExporter,
                "_normalize_pr_node",
                side_effect=lambda pr, repo, org: {
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
                    since=30,
                )
                batches = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        # Only one batch, limited by max_results and filter output
        assert len(batches) == 1
        assert len(batches[0]) == 2

        mock_filter.assert_called_once()
        # Ensure the GraphQL exporter uses "updatedAt" field for filtering
        assert mock_filter.call_args.args[1] == "updatedAt"

        mock_paginated.assert_called_once_with(
            LIST_PULL_REQUESTS_GQL,
            {
                "organization": "test-org",
                "repo": "repo1",
                "states": ["CLOSED"],
                "__path": "repository.pullRequests",
            },
        )
        assert mock_normalize.call_count == 2


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
            "commits": {"totalCount": 3},
        }

        normalized = exporter._normalize_pr_node(
            pr_node, repo_name="repo1", organization="test-org"
        )

        assert normalized["assignees"] == [{"login": "assignee"}]
        assert normalized["requested_reviewers"] == []
        assert normalized["comments"] == 5
        assert normalized["review_comments"] == 2
        assert normalized["commits"] == 3
        assert normalized["state"] == "open"
        assert normalized["__repository"] == "repo1"
        assert normalized["__organization"] == "test-org"

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
