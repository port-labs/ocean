"""Integration tests for the GraphQL field (property) reduction fallback.

When a PR list query keeps failing even after its page size bottoms out at the
floor, the client escalates to progressively lighter queries, dropping tiers of
expensive fields (``EXPENSIVE_PR_GRAPHQL_FIELD_TIERS``) until one succeeds, then
backfills the dropped fields per-PR.

These drive the real resync harness end-to-end (auth -> repo list -> PR
pagination -> raw items handed to Port) and assert on the raw items extracted. The failure is a
200 carrying unknown (non-ignored) errors — the "query too heavy" signal that
recovers purely at the client level, with no transport backoff (a gateway 5xx
would drag the harness through real retry sleeps; that path lives in the
client/transport unit tests).
"""

import os

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
    """Field-tier reduction, observed through the raw PR items handed to Port."""

    async def _resync(self, transport: InterceptTransport) -> ResyncResult:
        harness = IntegrationTestHarness(
            integration_path=INTEGRATION_PATH,
            port_mapping_config=mapping_for_kind("pull-request-graphql"),
            third_party_transport=transport,
            config_overrides=integration_config(),
        )
        try:
            await harness.start()
            return await harness.trigger_resync()
        finally:
            await harness.shutdown()

    @staticmethod
    def _pr_keys(result: ResyncResult) -> set[tuple[str, int]]:
        return {
            (item["__repository"], item["number"])
            for item in result.raw_items("pull-request")
        }

    @staticmethod
    def _expected_pr_keys() -> set[tuple[str, int]]:
        return {(repo, 1) for repo in REPO_NAMES}

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
        assert self._pr_keys(result) == self._expected_pr_keys()

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

        # Raw PRs being extracted means escalation dropped both tiers — a single-tier
        # strip would still carry `commits` and keep failing.
        assert result.errors == [], f"Resync had errors: {result.errors}"
        assert self._pr_keys(result) == self._expected_pr_keys()

    async def test_backfills_dropped_field_into_raw_item(self) -> None:
        """A field dropped by the winning fallback is refetched per-PR and merged."""
        # The list payload never carries `labels`; only the per-PR backfill can
        # put it on the raw item, so a `labels` value proves the merge ran.
        transport = (
            GithubMockTransportBuilder()
            .with_base()
            .fail_list_prs_when_query_has("reviewRequests")
            .succeed_list_prs()
            .respond_pr_details({"labels": {"nodes": [{"name": "bug"}]}})
            .build(strict=False)
        )

        result = await self._resync(transport)

        assert result.errors == [], f"Resync had errors: {result.errors}"
        prs = result.raw_items("pull-request")
        assert self._pr_keys(result) == self._expected_pr_keys()
        # Normalization flattens `labels.nodes` to `labels`, so the item holds a list.
        assert all(pr.get("labels") == [{"name": "bug"}] for pr in prs), prs

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
