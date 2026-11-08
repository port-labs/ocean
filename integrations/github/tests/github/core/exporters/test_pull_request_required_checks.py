from typing import Any, AsyncGenerator, Optional
from unittest.mock import AsyncMock, patch

import pytest

from github.clients.http.graphql_client import GithubGraphQLClient
from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.pull_request_exporter import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
from github.core.exporters.pull_request_exporter.required_checks import (
    ExpectedCheck,
    GraphQLRequiredChecksEnricher,
    ObservedCheck,
    check_run_outcome,
    status_context_outcome,
    summarize_required_checks,
)
from github.core.options import ListPullRequestOptions, SinglePullRequestOptions
from github.helpers.gql_queries import generate_pull_requests_required_checks_gql
from port_ocean.context.event import event_context

AVIATOR = "aviator/checks"
GATE = "Wait For Required Checks"


def _summarize(
    expected: list[ExpectedCheck],
    observed: list[ObservedCheck],
    ignore: Optional[list[str]] = None,
) -> Any:
    return summarize_required_checks(
        expected=expected, observed=observed, ignore=ignore or [], sha="abc"
    )


class TestOutcomes:
    @pytest.mark.parametrize(
        "status, conclusion, expected",
        [
            ("completed", "success", "success"),
            ("COMPLETED", "SKIPPED", "success"),
            ("completed", "neutral", "success"),
            ("completed", "failure", "failure"),
            ("COMPLETED", "TIMED_OUT", "failure"),
            ("completed", "cancelled", "failure"),
            ("COMPLETED", "ACTION_REQUIRED", "failure"),
            ("in_progress", None, "pending"),
            ("QUEUED", None, "pending"),
            ("completed", None, "pending"),
        ],
    )
    def test_check_run_outcome(
        self, status: str, conclusion: Optional[str], expected: str
    ) -> None:
        assert check_run_outcome(status, conclusion) == expected

    @pytest.mark.parametrize(
        "state, expected",
        [
            ("success", "success"),
            ("SUCCESS", "success"),
            ("failure", "failure"),
            ("ERROR", "failure"),
            ("pending", "pending"),
            ("EXPECTED", "pending"),
            (None, "pending"),
        ],
    )
    def test_status_context_outcome(self, state: Optional[str], expected: str) -> None:
        assert status_context_outcome(state) == expected


class TestSummarizeRequiredChecks:
    def test_ignored_pending_check_does_not_block_success(self) -> None:
        summary = _summarize(
            [ExpectedCheck(GATE), ExpectedCheck(AVIATOR)],
            [
                ObservedCheck(GATE, "success"),
                ObservedCheck(AVIATOR, "pending"),
            ],
            ignore=[AVIATOR],
        )

        assert summary.status == "success"
        assert summary.failing == []
        assert summary.pending == []
        assert summary.sha == "abc"

    def test_without_ignore_the_pending_check_blocks(self) -> None:
        summary = _summarize(
            [ExpectedCheck(GATE), ExpectedCheck(AVIATOR)],
            [ObservedCheck(GATE, "success"), ObservedCheck(AVIATOR, "pending")],
        )

        assert summary.status == "pending"
        assert summary.pending == [AVIATOR]

    def test_failure_takes_precedence_over_pending(self) -> None:
        summary = _summarize(
            [ExpectedCheck("lint"), ExpectedCheck("test")],
            [ObservedCheck("lint", "failure"), ObservedCheck("test", "pending")],
        )

        assert summary.status == "failure"
        assert summary.failing == ["lint"]
        assert summary.pending == ["test"]

    def test_expected_check_not_reported_yet_is_pending(self) -> None:
        summary = _summarize(
            [ExpectedCheck("lint"), ExpectedCheck("test")],
            [ObservedCheck("lint", "success")],
        )

        assert summary.status == "pending"
        assert summary.pending == ["test"]

    def test_optional_failing_check_is_ignored(self) -> None:
        summary = _summarize(
            [ExpectedCheck("lint")],
            [ObservedCheck("lint", "success"), ObservedCheck("wiz", "failure")],
        )

        assert summary.status == "success"
        assert summary.failing == []

    def test_no_required_checks_is_none(self) -> None:
        summary = _summarize([], [ObservedCheck("wiz", "failure")])

        assert summary.status == "none"

    def test_only_ignored_required_checks_is_none(self) -> None:
        summary = _summarize(
            [ExpectedCheck(AVIATOR)],
            [ObservedCheck(AVIATOR, "pending")],
            ignore=[AVIATOR],
        )

        assert summary.status == "none"

    def test_ignore_supports_glob_patterns(self) -> None:
        summary = _summarize(
            [ExpectedCheck("aviator/checks"), ExpectedCheck("aviator/other")],
            [],
            ignore=["aviator/*"],
        )

        assert summary.status == "none"

    def test_check_from_another_app_does_not_satisfy_the_requirement(self) -> None:
        summary = _summarize(
            [ExpectedCheck("build", app_id=15368)],
            [ObservedCheck("build", "success", app_id=999)],
        )

        assert summary.status == "pending"
        assert summary.pending == ["build"]

    @pytest.mark.parametrize("app_id", [None, 0, -1])
    def test_expected_check_without_a_specific_app_accepts_any_app(
        self, app_id: Optional[int]
    ) -> None:
        summary = _summarize(
            [ExpectedCheck("build", app_id=app_id)],
            [ObservedCheck("build", "success", app_id=999)],
        )

        assert summary.status == "success"

    def test_explicit_is_required_flag_wins_over_expected_matching(self) -> None:
        summary = _summarize(
            [],
            [
                ObservedCheck("build", "failure", is_required=True),
                ObservedCheck("wiz", "failure", is_required=False),
            ],
        )

        assert summary.status == "failure"
        assert summary.failing == ["build"]

    def test_same_check_reported_twice_uses_the_worst_outcome(self) -> None:
        summary = _summarize(
            [ExpectedCheck("build")],
            [ObservedCheck("build", "success"), ObservedCheck("build", "failure")],
        )

        assert summary.status == "failure"


def _gql_pr_node(
    number: int,
    contexts: list[dict[str, Any]],
    *,
    required_contexts: list[str],
    sha: str = "gqlsha",
    next_cursor: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "number": number,
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
    name: str, status: str, conclusion: Optional[str], required: bool
) -> dict[str, Any]:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "isRequired": required,
    }


def _gql_response(**aliased_nodes: Any) -> dict[str, Any]:
    return {"data": {"repository": aliased_nodes}}


@pytest.mark.asyncio
class TestGraphQLRequiredChecksEnricher:
    async def test_uses_is_required_and_ignores_the_ignored_check(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", [AVIATOR]
        )
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
                    "isRequired": False,
                },
            ],
            required_contexts=[GATE, AVIATOR],
        )

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(return_value=_gql_response(pr_7=node)),
        ):
            [pr] = await enricher.enrich([{"number": 7}])

        assert pr["required_checks_status"] == "success"
        assert pr["required_checks_failing"] == []
        assert pr["required_checks_pending"] == []
        assert pr["required_checks_sha"] == "gqlsha"

    async def test_reports_failing_required_status_context(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
        node = _gql_pr_node(
            7,
            [
                {
                    "__typename": "StatusContext",
                    "context": "legacy/ci",
                    "state": "ERROR",
                    "isRequired": True,
                }
            ],
            required_contexts=["legacy/ci"],
        )

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(return_value=_gql_response(pr_7=node)),
        ):
            [pr] = await enricher.enrich([{"number": 7}])

        assert pr["required_checks_status"] == "failure"
        assert pr["required_checks_failing"] == ["legacy/ci"]

    async def test_required_check_not_reported_yet_is_pending(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
        node = _gql_pr_node(7, [], required_contexts=["build"])

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(return_value=_gql_response(pr_7=node)),
        ):
            [pr] = await enricher.enrich([{"number": 7}])

        assert pr["required_checks_status"] == "pending"
        assert pr["required_checks_pending"] == ["build"]

    async def test_follows_the_contexts_cursor_of_large_pull_requests(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
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

        with patch.object(graphql_client, "send_api_request", send_api_request):
            [pr] = await enricher.enrich([{"number": 7}])

        assert send_api_request.await_count == 2
        second_query = send_api_request.await_args_list[1].kwargs["json_data"]["query"]
        assert 'after: "cursor-1"' in second_query
        assert pr["required_checks_status"] == "failure"
        assert pr["required_checks_failing"] == ["test"]

    async def test_batches_pull_requests_into_aliased_queries(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )
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
        with patch.object(graphql_client, "send_api_request", send_api_request):
            prs = await enricher.enrich([{"number": number} for number in numbers])

        assert send_api_request.await_count == 2
        assert {pr["required_checks_status"] for pr in prs} == {"success"}

    async def test_failed_query_leaves_status_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            [pr] = await enricher.enrich([{"number": 7}])

        assert pr["required_checks_status"] is None
        assert pr["required_checks_failing"] is None

    async def test_missing_pull_request_leaves_status_unknown(
        self, graphql_client: GithubGraphQLClient
    ) -> None:
        enricher = GraphQLRequiredChecksEnricher(
            graphql_client, "test-org", "repo1", []
        )

        with patch.object(
            graphql_client,
            "send_api_request",
            AsyncMock(return_value=_gql_response(pr_7=None)),
        ):
            [pr] = await enricher.enrich([{"number": 7}])

        assert pr["required_checks_status"] is None


class TestRequiredChecksQuery:
    def test_selects_is_required_for_each_pull_request_number(self) -> None:
        query = generate_pull_requests_required_checks_gql({3: None, 9: "abc"})

        assert "pr_3: pullRequest(number: 3)" in query
        assert "pr_9: pullRequest(number: 9)" in query
        assert "isRequired(pullRequestNumber: 3)" in query
        assert "isRequired(pullRequestNumber: 9)" in query
        assert 'after: "abc"' in query
        assert query.count('after: "abc"') == 1


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
                    required_checks_ignore=[AVIATOR],
                )
            )

        enricher_cls.assert_called_once_with(
            graphql_client, "test-org", "repo1", [AVIATOR]
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

        enrich = AsyncMock(side_effect=lambda prs: prs)
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
                            required_checks_ignore=[AVIATOR],
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
                    required_checks_ignore=[AVIATOR],
                )
            )

        assert result is not None
        assert "required_checks_status" not in result
