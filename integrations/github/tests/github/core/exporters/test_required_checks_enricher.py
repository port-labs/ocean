from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.pull_request_exporter import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
from github.core.exporters.pull_request_exporter.required_checks_enricher import (
    MAX_CONTEXT_PAGES_PER_PR,
    GraphQLRequiredChecksEnricher,
)
from github.core.options import ListPullRequestOptions, SinglePullRequestOptions
from github.helpers.exceptions import GraphQLClientError, GraphQLErrorGroup
from github.helpers.gql_queries import generate_pull_requests_required_checks_gql
from port_ocean.context.event import event_context

AVIATOR = "aviator/checks"
GATE = "Wait For Required Checks"

EARLIER = "2026-11-08T10:00:00Z"
LATER = "2026-11-08T11:00:00Z"


def _gql_pr_node(
    number: int,
    contexts: list[dict[str, Any]],
    *,
    required_contexts: list[str],
    sha: str = "gqlsha",
    next_cursor: Optional[str] = None,
    state: str = "OPEN",
) -> dict[str, Any]:
    return {
        "number": number,
        "state": state,
        "headRefOid": sha,
        "baseRef": {
            "refUpdateRule": {"requiredStatusCheckContexts": required_contexts}
        },
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": sha,
                        "statusCheckRollup": {
                            "contexts": {
                                "pageInfo": {
                                    "hasNextPage": next_cursor is not None,
                                    "endCursor": next_cursor,
                                },
                                "nodes": contexts,
                            }
                        },
                    }
                }
            ]
        },
    }


def _check_run(
    name: str,
    status: str,
    conclusion: Optional[str],
    required: Optional[bool],
    started_at: Optional[str] = EARLIER,
) -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "startedAt": started_at,
        "isRequired": required,
    }


def _gql_response(**aliased_nodes: Any) -> dict[str, Any]:
    return {"data": {"repository": aliased_nodes}}


def _heavy_query_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.github.com/graphql")
    return httpx.HTTPStatusError(
        "timeout", request=request, response=httpx.Response(504, request=request)
    )


async def _enrich_one(
    graphql_client: GithubGraphQLClient,
    send_api_request: Any,
    excluded: Optional[list[str]] = None,
    pull_request: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    pull_request = pull_request or {"number": 7}
    enricher = GraphQLRequiredChecksEnricher(
        graphql_client, "test-org", "repo1", excluded or []
    )
    with patch.object(graphql_client, "send_api_request", send_api_request):
        await enricher.enrich([pull_request])
    return pull_request


@pytest.mark.asyncio
class TestGraphQLRequiredChecksEnricher:
    async def test_uses_is_required_and_ignores_the_ignored_check(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(
            7,
            [
                _check_run(GATE, "COMPLETED", "SKIPPED", True),
                _check_run(AVIATOR, "IN_PROGRESS", None, True),
                _check_run("Wiz", "COMPLETED", "FAILURE", False),
                {
                    "__typename": "StatusContext",
                    "context": "legacy/ci",
                    "state": "FAILURE",
                    "createdAt": EARLIER,
                    "isRequired": False,
                },
            ],
            required_contexts=[GATE, AVIATOR],
        )

        pr = await _enrich_one(
            graphql_client,
            AsyncMock(return_value=_gql_response(pr_7=node)),
            excluded=[AVIATOR],
        )

        assert pr["required_checks_status"] == "success"
        assert pr["required_checks_failing"] == []
        assert pr["required_checks_pending"] == []
        assert pr["required_checks_sha"] == "gqlsha"

    async def test_enriches_the_pull_requests_in_place(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
        pull_requests = [{"number": 7}]
        node = _gql_pr_node(7, [], required_contexts=[])

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(return_value=_gql_response(pr_7=node)),
        ):
            await enricher.enrich(pull_requests)

        assert pull_requests[0]["required_checks_status"] == "no_required_checks"

    async def test_reports_failing_required_status_context(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(
            7,
            [
                {
                    "__typename": "StatusContext",
                    "context": "legacy/ci",
                    "state": "ERROR",
                    "createdAt": EARLIER,
                    "isRequired": True,
                }
            ],
            required_contexts=["legacy/ci"],
        )

        pr = await _enrich_one(
            graphql_client, AsyncMock(return_value=_gql_response(pr_7=node))
        )

        assert pr["required_checks_status"] == "failure"
        assert pr["required_checks_failing"] == ["legacy/ci"]

    async def test_required_check_not_reported_yet_is_pending(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(7, [], required_contexts=["build"])

        pr = await _enrich_one(
            graphql_client, AsyncMock(return_value=_gql_response(pr_7=node))
        )

        assert pr["required_checks_status"] == "pending"
        assert pr["required_checks_pending"] == ["build"]

    async def test_superseded_failed_run_does_not_fail_the_pull_request(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(
            7,
            [
                _check_run("build", "COMPLETED", "FAILURE", True, EARLIER),
                _check_run("build", "COMPLETED", "SUCCESS", True, LATER),
            ],
            required_contexts=["build"],
        )

        pr = await _enrich_one(
            graphql_client, AsyncMock(return_value=_gql_response(pr_7=node))
        )

        assert pr["required_checks_status"] == "success"
        assert pr["required_checks_failing"] == []

    async def test_follows_the_contexts_cursor_of_large_pull_requests(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        first = _gql_pr_node(
            7,
            [_check_run("lint", "COMPLETED", "SUCCESS", True)],
            required_contexts=["lint", "test"],
            next_cursor="cursor-1",
        )
        second = _gql_pr_node(
            7,
            [_check_run("test", "COMPLETED", "FAILURE", True)],
            required_contexts=["lint", "test"],
        )
        send_api_request = AsyncMock(
            side_effect=[_gql_response(pr_7=first), _gql_response(pr_7=second)]
        )

        pr = await _enrich_one(graphql_client, send_api_request)

        assert send_api_request.await_count == 2
        second_query = send_api_request.await_args_list[1].kwargs["json_data"]["query"]
        assert 'after: "cursor-1"' in second_query
        assert pr["required_checks_status"] == "failure"
        assert pr["required_checks_failing"] == ["test"]

    async def test_pages_of_checks_are_requested_through_the_first_variable(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(7, [], required_contexts=[])
        send_api_request = AsyncMock(return_value=_gql_response(pr_7=node))

        await _enrich_one(graphql_client, send_api_request)

        kwargs = send_api_request.await_args_list[0].kwargs
        assert kwargs["json_data"]["variables"]["first"] == 100
        assert "contexts(first: $first)" in kwargs["json_data"]["query"]
        assert kwargs["query_path"]

    async def test_batches_pull_requests_into_aliased_queries(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        numbers = list(range(1, 8))

        async def fake_send(*_: Any, **kwargs: Any) -> dict[str, Any]:
            query = kwargs["json_data"]["query"]
            return _gql_response(
                **{
                    f"pr_{number}": _gql_pr_node(
                        number,
                        [_check_run("build", "COMPLETED", "SUCCESS", True)],
                        required_contexts=["build"],
                    )
                    for number in numbers
                    if f"pr_{number}:" in query
                }
            )

        send_api_request = AsyncMock(side_effect=fake_send)
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
        prs = [{"number": number} for number in numbers]
        with patch.object(graphql_client, "send_api_request", send_api_request):
            await enricher.enrich(prs)

        assert send_api_request.await_count == 2
        assert {pr["required_checks_status"] for pr in prs} == {"success"}

    async def test_failed_query_leaves_status_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        send_api_request = AsyncMock(side_effect=httpx.ConnectError("boom"))

        pr = await _enrich_one(graphql_client, send_api_request)

        assert pr["required_checks_status"] == "unknown"
        assert pr["required_checks_failing"] is None
        # Not a size problem, so it is not retried.
        assert send_api_request.await_count == 1

    async def test_unexpected_errors_are_not_swallowed(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        send_api_request = AsyncMock(side_effect=RuntimeError("bug"))

        with pytest.raises(RuntimeError, match="bug"):
            await _enrich_one(graphql_client, send_api_request)

    async def test_missing_pull_request_leaves_status_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        pr = await _enrich_one(
            graphql_client, AsyncMock(return_value=_gql_response(pr_7=None))
        )

        assert pr["required_checks_status"] == "unknown"

    async def test_pull_request_that_is_no_longer_open_is_left_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(7, [], required_contexts=["build"], state="MERGED")

        pr = await _enrich_one(
            graphql_client, AsyncMock(return_value=_gql_response(pr_7=node))
        )

        assert pr["required_checks_status"] == "unknown"

    async def test_check_with_unknown_is_required_leaves_status_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(
            7,
            [
                _check_run("build", "COMPLETED", "SUCCESS", None),
                _check_run("lint", "COMPLETED", "SUCCESS", True),
            ],
            required_contexts=["build", "lint"],
        )

        pr = await _enrich_one(
            graphql_client, AsyncMock(return_value=_gql_response(pr_7=node))
        )

        assert pr["required_checks_status"] == "unknown"
        assert pr["required_checks_pending"] is None


@pytest.mark.asyncio
class TestGraphQLRequiredChecksEnricherBackoff:
    async def test_retries_with_smaller_pages_of_checks_when_the_query_errors(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(
            7,
            [_check_run("build", "COMPLETED", "SUCCESS", True)],
            required_contexts=["build"],
        )
        send_api_request = AsyncMock(
            side_effect=[
                GraphQLErrorGroup([GraphQLClientError("too heavy")]),
                _gql_response(pr_7=node),
            ]
        )

        pr = await _enrich_one(graphql_client, send_api_request)

        page_sizes = [
            call.kwargs["json_data"]["variables"]["first"]
            for call in send_api_request.await_args_list
        ]
        assert page_sizes == [100, 50]
        assert pr["required_checks_status"] == "success"

    async def test_splits_the_pull_requests_when_a_query_times_out(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        async def fake_send(*_: Any, **kwargs: Any) -> dict[str, Any]:
            query = kwargs["json_data"]["query"]
            numbers = [n for n in range(1, 6) if f"pr_{n}:" in query]
            if len(numbers) > 1:
                raise _heavy_query_error()
            return _gql_response(
                **{
                    f"pr_{n}": _gql_pr_node(
                        n,
                        [_check_run("build", "COMPLETED", "SUCCESS", True)],
                        required_contexts=["build"],
                    )
                    for n in numbers
                }
            )

        send_api_request = AsyncMock(side_effect=fake_send)
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
        prs = [{"number": number} for number in range(1, 6)]
        with patch.object(graphql_client, "send_api_request", send_api_request):
            await enricher.enrich(prs)

        assert {pr["required_checks_status"] for pr in prs} == {"success"}

    async def test_a_persistent_graphql_error_does_not_walk_the_ladder_at_every_split(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        send_api_request = AsyncMock(
            side_effect=GraphQLErrorGroup([GraphQLClientError("too heavy")])
        )
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
        prs: list[dict[str, Any]] = [{"number": number} for number in range(1, 6)]

        with patch.object(graphql_client, "send_api_request", send_api_request):
            await enricher.enrich(prs)

        # 5 pull requests split into 1 + 1 + 1 + 1 + 1 over 4 splits: one query per
        # split, and the four page sizes only for each single pull request.
        assert send_api_request.await_count == 4 + 5 * 4
        assert {pr["required_checks_status"] for pr in prs} == {"unknown"}

    async def test_several_pull_requests_are_queried_at_the_full_page_size_only(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        send_api_request = AsyncMock(
            side_effect=GraphQLErrorGroup([GraphQLClientError("too heavy")])
        )
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )

        with patch.object(graphql_client, "send_api_request", send_api_request):
            await enricher.enrich([{"number": 1}, {"number": 2}])

        sizes = [
            call.kwargs["json_data"]["variables"]["first"]
            for call in send_api_request.await_args_list
        ]
        # One attempt for the pair, then the ladder for each pull request on its own.
        assert sizes == [100] + [100, 50, 25, 10] * 2

    async def test_a_single_pull_request_that_is_too_heavy_is_left_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        send_api_request = AsyncMock(side_effect=_heavy_query_error())

        pr = await _enrich_one(graphql_client, send_api_request)

        assert pr["required_checks_status"] == "unknown"
        assert send_api_request.await_count == 1

    async def test_stops_following_cursors_after_the_page_limit(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        calls = 0

        async def fake_send(*_: Any, **__: Any) -> dict[str, Any]:
            nonlocal calls
            calls += 1
            return _gql_response(
                pr_7=_gql_pr_node(
                    7,
                    [_check_run(f"check-{calls}", "COMPLETED", "SUCCESS", True)],
                    required_contexts=[],
                    next_cursor=f"cursor-{calls}",
                )
            )

        pr = await _enrich_one(graphql_client, AsyncMock(side_effect=fake_send))

        assert calls == MAX_CONTEXT_PAGES_PER_PR
        assert pr["required_checks_status"] == "unknown"

    async def test_stops_when_the_cursor_does_not_advance(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        node = _gql_pr_node(
            7,
            [_check_run("build", "COMPLETED", "SUCCESS", True)],
            required_contexts=["build"],
            next_cursor="stuck",
        )
        send_api_request = AsyncMock(return_value=_gql_response(pr_7=node))

        pr = await _enrich_one(graphql_client, send_api_request)

        assert send_api_request.await_count == 2
        assert pr["required_checks_status"] == "unknown"


class TestRequiredChecksQuery:
    def test_selects_is_required_for_each_pull_request_number(self) -> None:
        query = generate_pull_requests_required_checks_gql({3: None, 9: "abc"})

        assert "pr_3: pullRequest(number: 3)" in query
        assert "pr_9: pullRequest(number: 9)" in query
        assert "isRequired(pullRequestNumber: 3)" in query
        assert "isRequired(pullRequestNumber: 9)" in query
        assert 'after: "abc"' in query
        assert query.count('after: "abc"') == 1

    def test_declares_the_page_size_variable_and_the_fields_needed_for_latest_wins(
        self,
    ) -> None:
        query = generate_pull_requests_required_checks_gql({3: None})

        assert "$first: Int!" in query
        assert "contexts(first: $first)" in query
        assert "startedAt" in query
        assert "createdAt" in query
        assert "state" in query


@pytest.mark.asyncio
class TestExportersRequiredChecks:
    async def test_graphql_get_resource_enriches_open_pull_requests(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)
        pr_node = {"id": 1, "number": 7, "state": "OPEN"}

        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.GraphQLRequiredChecksEnricher"
            ) as enricher_cls,
            patch.object(
                graphql_client,
                "send_api_request",
                AsyncMock(
                    return_value={"data": {"repository": {"pullRequest": pr_node}}}
                ),
            ),
        ):
            enricher_cls.return_value.enrich = AsyncMock()
            await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    repo={"name": "repo1"},
                    include_required_checks_status=True,
                    excluded_required_checks=[AVIATOR],
                )
            )

        enricher_cls.assert_called_once_with(
            graphql_client, "test-org", "repo1", [AVIATOR]
        )
        enricher_cls.return_value.enrich.assert_awaited_once()

    async def test_graphql_get_resource_still_enriches_when_state_is_excluded(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)
        pr_node = {"id": 1, "number": 7}

        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.GraphQLRequiredChecksEnricher"
            ) as enricher_cls,
            patch.object(
                graphql_client,
                "send_api_request",
                AsyncMock(
                    return_value={"data": {"repository": {"pullRequest": pr_node}}}
                ),
            ),
        ):
            enricher_cls.return_value.enrich = AsyncMock()
            await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    repo={"name": "repo1"},
                    exclude_graphql_fields=["state"],
                    include_required_checks_status=True,
                )
            )

        enricher_cls.return_value.enrich.assert_awaited_once()

    async def test_graphql_get_resource_is_not_enriched_when_disabled_or_closed(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)

        for state, include in (("OPEN", False), ("CLOSED", True), ("MERGED", True)):
            pr_node = {"id": 1, "number": 7, "state": state}
            with (
                patch(
                    "github.core.exporters.pull_request_exporter.core.GraphQLRequiredChecksEnricher"
                ) as enricher_cls,
                patch.object(
                    graphql_client,
                    "send_api_request",
                    AsyncMock(
                        return_value={"data": {"repository": {"pullRequest": pr_node}}}
                    ),
                ),
            ):
                await exporter.get_resource(
                    SinglePullRequestOptions(
                        organization="test-org",
                        repo_name="repo1",
                        pr_number=7,
                        repo={"name": "repo1"},
                        include_required_checks_status=include,
                    )
                )

            enricher_cls.assert_not_called()

    async def test_graphql_paginated_enriches_open_batches_but_not_closed(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        exporter = GraphQLPullRequestExporter(graphql_client)
        open_pr = {"number": 1, "state": "open"}
        closed_pr = {"number": 2, "state": "closed"}

        async def open_batches(*_: Any, **__: Any) -> AsyncGenerator[Any, None]:
            yield [open_pr]

        async def closed_batches(*_: Any, **__: Any) -> AsyncGenerator[Any, None]:
            yield [closed_pr]

        enrich = AsyncMock()
        with (
            patch(
                "github.core.exporters.pull_request_exporter.core.GraphQLRequiredChecksEnricher"
            ) as enricher_cls,
            patch.object(exporter, "_fetch_open_pull_requests", open_batches),
            patch.object(exporter, "_fetch_closed_pull_requests", closed_batches),
        ):
            enricher_cls.return_value.enrich = enrich
            async with event_context("test-event"):
                batches = [
                    batch
                    async for batch in exporter.get_paginated_resources(
                        ListPullRequestOptions(
                            organization="test-org",
                            repo_name="repo1",
                            repo={"name": "repo1"},
                            states=["open", "closed"],
                            max_results=None,
                            include_required_checks_status=True,
                            excluded_required_checks=[AVIATOR],
                        )
                    )
                ]

        assert batches == [[open_pr], [closed_pr]]
        enricher_cls.assert_called_once_with(
            graphql_client, "test-org", "repo1", [AVIATOR]
        )
        enrich.assert_awaited_once_with([open_pr])

    async def test_rest_exporter_ignores_the_required_checks_options(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)
        pull_request = {"id": 1, "number": 7, "state": "open"}

        with patch.object(
            rest_client, "send_api_request", AsyncMock(return_value=pull_request)
        ):
            result = await exporter.get_resource(
                SinglePullRequestOptions(
                    organization="test-org",
                    repo_name="repo1",
                    pr_number=7,
                    include_required_checks_status=True,
                    excluded_required_checks=[AVIATOR],
                )
            )

        assert result is not None
        assert "required_checks_status" not in result

    async def test_rest_exporter_warns_once_when_required_checks_are_requested(
        self, rest_client: GithubRestClient
    ) -> None:
        exporter = RestPullRequestExporter(rest_client)
        pull_request = {"id": 1, "number": 7, "state": "open"}

        with (
            patch.object(
                rest_client, "send_api_request", AsyncMock(return_value=pull_request)
            ),
            patch(
                "github.core.exporters.pull_request_exporter.core.logger"
            ) as mock_logger,
        ):
            for _ in range(2):
                await exporter.get_resource(
                    SinglePullRequestOptions(
                        organization="test-org",
                        repo_name="repo1",
                        pr_number=7,
                        include_required_checks_status=True,
                    )
                )

        mock_logger.warning.assert_called_once()
        assert "only supported with api: graphql" in str(mock_logger.warning.call_args)
