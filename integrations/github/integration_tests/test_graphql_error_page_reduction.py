"""Integration tests for the client-level GraphQL page-size backoff.

GitHub sometimes answers a GraphQL query with HTTP 200 whose body still carries
unknown (non-ignored) errors on large pages. GithubGraphQLClient.send_paginated_request
recovers by shrinking `variables.first` and retrying until the page succeeds or
reaches its floor.

Unlike the transport-layer 5xx backoff, this path lives above the transport, so
it runs through the real resync harness end-to-end (auth -> exporter ->
pagination -> Port entities).
"""

import os
from typing import Any, Callable

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from helpers import integration_config, mapping_for_kind
from mocks.graphql_payloads import ORG_MEMBERS, org_members_graphql_response
from mocks.transport_builder import GithubMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# `send_paginated_request` builds the first page at PAGE_SIZE and steps down by 5.
FULL_PAGE_SIZE = 25
UNKNOWN_ERROR_BODY: dict[str, Any] = {
    "errors": [{"message": "something went wrong", "type": "UNKNOWN"}]
}


async def _run_user_resync(
    org_members_response: Callable[[dict[str, Any]], dict[str, Any]],
) -> ResyncResult:
    """Resync the `user` kind, whose org-member fetch paginates over GraphQL."""
    builder = GithubMockTransportBuilder().with_base()
    builder.add_graphql_route("OrgMemberQuery", org_members_response)
    transport = builder.build(strict=False)

    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_for_kind("user"),
        third_party_transport=transport,
        config_overrides=integration_config(),
    )
    try:
        await harness.start()
        return await harness.trigger_resync()
    finally:
        await harness.shutdown()


class TestGraphQLUnknownErrorResync:
    @pytest.mark.asyncio
    async def test_recovers_at_reduced_page_size(self) -> None:
        """A 200-with-unknown-errors at the full page shrinks `first` and recovers."""
        sent_first: list[int | None] = []

        def respond(variables: dict[str, Any]) -> dict[str, Any]:
            first = variables.get("first")
            sent_first.append(first)
            if first is not None and first >= FULL_PAGE_SIZE:
                return UNKNOWN_ERROR_BODY
            return org_members_graphql_response(variables)

        result = await _run_user_resync(respond)

        assert result.errors == [], f"Resync had errors: {result.errors}"
        users = {
            e["identifier"]
            for e in result.upserted_entities
            if e["blueprint"] == "githubUser"
        }
        assert users == {member["login"] for member in ORG_MEMBERS}
        # Full page fails, one step down succeeds — no replays at the same size.
        assert sent_first == [FULL_PAGE_SIZE, FULL_PAGE_SIZE - 5]

    @pytest.mark.asyncio
    async def test_exhausts_to_floor_and_surfaces_error(self) -> None:
        """When every page size still errors, the walk reaches the floor and fails."""
        sent_first: list[int | None] = []

        def respond(variables: dict[str, Any]) -> dict[str, Any]:
            sent_first.append(variables.get("first"))
            return UNKNOWN_ERROR_BODY

        result = await _run_user_resync(respond)

        assert result.errors, "Expected the exhausted reduction to surface an error"
        # 25 -> 20 -> 15 -> 10 -> 5 -> 1, then the floor stops further retries.
        assert sent_first == [25, 20, 15, 10, 5, 1]
