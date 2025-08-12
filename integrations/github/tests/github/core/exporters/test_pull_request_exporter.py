from typing import Any, AsyncGenerator
import pytest
from unittest.mock import patch, AsyncMock
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.clients.http.rest_client import GithubRestClient
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
                SinglePullRequestOptions(repo_name="repo1", pr_number=101)
            )

            expected_pr = {**TEST_PULL_REQUESTS[0], "__repository": "repo1"}
            assert pr == expected_pr

            mock_request.assert_called_once_with(
                f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/pulls/101"
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
                    states=states, repo_name="repo1", max_results=10
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
                    f"{rest_client.base_url}/repos/{rest_client.organization}/repo1/pulls",
                    params,
                )
                for params in expected_calls
            ]
            assert actual_calls == expected_call_args

    async def test_get_paginated_resources_respects_max_results(
        self, rest_client: GithubRestClient
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
                    states=["closed"], repo_name="repo1", max_results=5
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
                    states=["closed"], repo_name="repo1", max_results=5
                )
                results = [
                    batch async for batch in exporter.get_paginated_resources(options)
                ]

        flat_results = [pr for batch in results for pr in batch]
        assert len(flat_results) == 5
        # Should be first 3 from batch1 + first 2 from batch2
        expected_prs = many_prs[:3] + many_prs[3:5]
        assert flat_results == [{**pr, "__repository": "repo1"} for pr in expected_prs]
