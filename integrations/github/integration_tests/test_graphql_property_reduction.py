"""Integration tests for the GraphQL field (property) reduction fallback.

When a PR list query keeps failing even after its page size bottoms out at the
floor, ``send_paginated_request`` escalates to progressively lighter queries,
dropping tiers of expensive fields (``EXPENSIVE_PR_GRAPHQL_FIELD_TIERS``) until
the page succeeds or the fallbacks run out.

These drive the real resync harness end-to-end (auth -> repo list -> PR
pagination -> Port entities). The trigger is a 200 carrying unknown (non-ignored)
errors — the "query too heavy" signal that recovers purely at the client level,
with no transport backoff (a gateway 5xx would drag the harness through real
retry sleeps; that path is covered by the client/transport unit tests instead).
The error is keyed off query *content*, not page size, so the assertions hold
regardless of the page-size walk that runs first.
"""

import json
import os
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from helpers import integration_config, mapping_for_kind
from mocks.graphql_payloads import pull_requests_graphql_response
from mocks.payloads import REPO_NAMES
from mocks.transport_builder import GithubMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# A 200 whose body still carries unknown (non-ignored) errors.
UNKNOWN_200_ERROR: dict[str, Any] = {
    "status_code": 200,
    "json": {"errors": [{"message": "something went wrong", "type": "UNKNOWN"}]},
}

# Representative field names from the first two tiers of
# EXPENSIVE_PR_GRAPHQL_FIELD_TIERS — their presence marks a query as still
# carrying that tier's expensive fields.
RELATION_TIER_MARKER = "reviewRequests"
COMMIT_TIER_MARKER = "commits"


def _graphql_query_matcher(operation: str) -> Callable[[httpx.Request], bool]:
    def matches(request: httpx.Request) -> bool:
        if "/graphql" not in str(request.url) or not request.content:
            return False
        return operation in json.loads(request.content).get("query", "")

    return matches


_is_list_prs = _graphql_query_matcher("ListPullRequests")
_is_pr_details = _graphql_query_matcher("PullRequestDetails")


def _pr_success(variables: dict[str, Any]) -> dict[str, Any]:
    return {"status_code": 200, "json": pull_requests_graphql_response(variables)}


async def _run_pr_resync(
    respond: Callable[[str, dict[str, Any]], dict[str, Any]],
    *,
    details_respond: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    mapping: dict[str, Any] | None = None,
) -> tuple[ResyncResult, list[str]]:
    """Resync the `pull-request` (graphql) kind, capturing every list query it sends.

    `respond`/`details_respond` receive the query text and variables and return an
    InterceptTransport response (`{"status_code", "json"}`). `details_respond`, when
    given, answers the single-PR backfill queries.
    """
    sent_queries: list[str] = []

    def route(request: httpx.Request) -> dict[str, Any]:
        body = json.loads(request.content)
        sent_queries.append(body.get("query", ""))
        return respond(body.get("query", ""), body.get("variables", {}))

    transport = GithubMockTransportBuilder().with_base().build(strict=False)
    transport.add_route("POST", _is_list_prs, route)
    if details_respond is not None:

        def details_route(request: httpx.Request) -> dict[str, Any]:
            body = json.loads(request.content)
            return details_respond(body.get("query", ""), body.get("variables", {}))

        transport.add_route("POST", _is_pr_details, details_route)

    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping or mapping_for_kind("pull-request-graphql"),
        third_party_transport=transport,
        config_overrides=integration_config(),
    )
    try:
        await harness.start()
        result = await harness.trigger_resync()
    finally:
        await harness.shutdown()
    return result, sent_queries


def _pr_identifiers(result: ResyncResult) -> set[str]:
    return {
        e["identifier"]
        for e in result.upserted_entities
        if e["blueprint"] == "githubPullRequest"
    }


class TestGraphQLPropertyReduction:
    @pytest.mark.asyncio
    async def test_recovers_by_stripping_first_tier(self) -> None:
        """A query failing with the relation tier present recovers once it's dropped."""

        def respond(query: str, variables: dict[str, Any]) -> dict[str, Any]:
            if RELATION_TIER_MARKER in query:
                return UNKNOWN_200_ERROR
            return _pr_success(variables)

        result, sent = await _run_pr_resync(respond)

        assert result.errors == [], f"Resync had errors: {result.errors}"
        assert len(_pr_identifiers(result)) == len(REPO_NAMES)
        # The full query (relation tier present) was tried, and the query that
        # finally succeeded had that tier stripped.
        assert any(RELATION_TIER_MARKER in q for q in sent)
        assert any(RELATION_TIER_MARKER not in q for q in sent)

    @pytest.mark.asyncio
    async def test_escalates_through_tiers_until_commits_dropped(self) -> None:
        """Escalation continues tier by tier: relations first, then commit fields."""

        def respond(query: str, variables: dict[str, Any]) -> dict[str, Any]:
            if RELATION_TIER_MARKER in query or COMMIT_TIER_MARKER in query:
                return UNKNOWN_200_ERROR
            return _pr_success(variables)

        result, sent = await _run_pr_resync(respond)

        assert result.errors == [], f"Resync had errors: {result.errors}"
        assert len(_pr_identifiers(result)) == len(REPO_NAMES)
        # An intermediate fallback (relations gone, commits still present) was
        # attempted before the one that finally dropped commits too.
        assert any(
            RELATION_TIER_MARKER not in q and COMMIT_TIER_MARKER in q for q in sent
        )
        assert any(
            RELATION_TIER_MARKER not in q and COMMIT_TIER_MARKER not in q for q in sent
        )

    @pytest.mark.asyncio
    async def test_backfills_stripped_fields_into_final_entity(self) -> None:
        """Fields dropped by the winning fallback are refetched per-PR and merged."""
        # Success payload never carries `labels`; only the per-PR details backfill
        # can put it on the entity, so seeing it proves the merge ran end to end.
        details_pr = {
            "labels": {"nodes": [{"name": "bug"}]},
        }

        def respond(query: str, variables: dict[str, Any]) -> dict[str, Any]:
            if RELATION_TIER_MARKER in query:
                return UNKNOWN_200_ERROR
            return _pr_success(variables)

        def details_respond(query: str, variables: dict[str, Any]) -> dict[str, Any]:
            return {
                "status_code": 200,
                "json": {"data": {"repository": {"pullRequest": details_pr}}},
            }

        # Normalization flattens `labels.nodes` to `labels`, so the entity sees a list.
        mapping = mapping_for_kind("pull-request-graphql")
        mapping["resources"][0]["port"]["entity"]["mappings"]["properties"][
            "label"
        ] = ".labels[0].name"

        result, _ = await _run_pr_resync(
            respond, details_respond=details_respond, mapping=mapping
        )

        assert result.errors == [], f"Resync had errors: {result.errors}"
        prs = [
            e for e in result.upserted_entities if e["blueprint"] == "githubPullRequest"
        ]
        assert prs, "expected PR entities"
        assert all(e["properties"].get("label") == "bug" for e in prs)

    @pytest.mark.asyncio
    async def test_exhausted_fallbacks_surface_error(self) -> None:
        """When every fallback still fails, the resync surfaces the error."""

        def respond(query: str, variables: dict[str, Any]) -> dict[str, Any]:
            return UNKNOWN_200_ERROR

        result, sent = await _run_pr_resync(respond)

        assert result.errors, "Expected exhausted field reduction to surface an error"
        # The primary query and at least one stripped fallback were both tried.
        assert any(RELATION_TIER_MARKER in q for q in sent)
        assert any(RELATION_TIER_MARKER not in q for q in sent)
