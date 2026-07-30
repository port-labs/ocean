"""Integration tests for the GraphQL field (property) reduction fallback.

When a PR list query keeps failing even after its page size bottoms out at the
floor, the client escalates to progressively lighter queries, dropping tiers of
expensive fields (``EXPENSIVE_PR_GRAPHQL_FIELD_TIERS``) until one succeeds, then
backfills the dropped fields per-PR.

These drive the real resync harness end-to-end (auth -> repo list -> PR
pagination -> Port entities) and assert on what reaches Port. The failure is a
200 carrying unknown (non-ignored) errors — the "query too heavy" signal that
recovers purely at the client level, with no transport backoff (a gateway 5xx
would drag the harness through real retry sleeps; that path lives in the
client/transport unit tests).
"""

import os
from typing import Any

import pytest

from port_ocean.integration_testing import (
    IntegrationTestHarness,
    InterceptTransport,
    ResyncResult,
)

from helpers import integration_config, mapping_for_kind
from mocks.payloads import REPO_NAMES
from mocks.transport_builder import GithubMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.asyncio
class TestGraphQLFieldReduction:
    """Field-tier reduction, observed through the PR entities that reach Port."""

    async def _resync(
        self,
        transport: InterceptTransport,
        mapping: dict[str, Any] | None = None,
    ) -> ResyncResult:
        harness = IntegrationTestHarness(
            integration_path=INTEGRATION_PATH,
            port_mapping_config=mapping or mapping_for_kind("pull-request-graphql"),
            third_party_transport=transport,
            config_overrides=integration_config(),
        )
        try:
            await harness.start()
            return await harness.trigger_resync()
        finally:
            await harness.shutdown()

    @staticmethod
    def _pr_identifiers(result: ResyncResult) -> set[str]:
        return {
            e["identifier"]
            for e in result.upserted_entities
            if e["blueprint"] == "githubPullRequest"
        }

    async def test_recovers_when_relation_tier_stripped(self) -> None:
        """Relation fields make the query fail; stripping them recovers all PRs."""
        transport = (
            GithubMockTransportBuilder()
            .with_base()
            .fail_list_prs_when_query_has("reviewRequests")
            .succeed_list_prs()
            .build(strict=False)
        )

        result = await self._resync(transport)

        assert result.errors == [], f"Resync had errors: {result.errors}"
        assert len(self._pr_identifiers(result)) == len(REPO_NAMES)

    async def test_escalates_until_commit_tier_stripped(self) -> None:
        """Only a query with both relation AND commit tiers stripped succeeds."""
        transport = (
            GithubMockTransportBuilder()
            .with_base()
            .fail_list_prs_when_query_has("reviewRequests")
            .fail_list_prs_when_query_has("commits")
            .succeed_list_prs()
            .build(strict=False)
        )

        result = await self._resync(transport)

        # PRs reaching Port means escalation dropped both tiers — a single-tier
        # strip would still carry `commits` and keep failing.
        assert result.errors == [], f"Resync had errors: {result.errors}"
        assert len(self._pr_identifiers(result)) == len(REPO_NAMES)

    async def test_backfills_dropped_field_into_entity(self) -> None:
        """A field dropped by the winning fallback is refetched per-PR and mapped."""
        # The list payload never carries `labels`; only the per-PR backfill can
        # put it on the entity, so a mapped `label` proves the merge ran.
        transport = (
            GithubMockTransportBuilder()
            .with_base()
            .fail_list_prs_when_query_has("reviewRequests")
            .succeed_list_prs()
            .respond_pr_details({"labels": {"nodes": [{"name": "bug"}]}})
            .build(strict=False)
        )
        # Normalization flattens `labels.nodes` to `labels`, so the entity sees a list.
        mapping = mapping_for_kind("pull-request-graphql")
        mapping["resources"][0]["port"]["entity"]["mappings"]["properties"][
            "label"
        ] = ".labels[0].name"

        result = await self._resync(transport, mapping)

        assert result.errors == [], f"Resync had errors: {result.errors}"
        prs = [
            e for e in result.upserted_entities if e["blueprint"] == "githubPullRequest"
        ]
        assert prs, "expected PR entities"
        assert all(e["properties"].get("label") == "bug" for e in prs)

    async def test_all_queries_failing_surfaces_error(self) -> None:
        """When no fallback recovers, the resync surfaces the error."""
        transport = (
            GithubMockTransportBuilder()
            .with_base()
            .fail_all_list_prs()
            .build(strict=False)
        )

        result = await self._resync(transport)

        assert result.errors, "Expected exhausted field reduction to surface an error"
