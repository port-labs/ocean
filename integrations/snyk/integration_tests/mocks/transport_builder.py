from typing import Any

import httpx

from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    ORG_ID,
    RECORD_COUNT,
    org_response,
    project_response,
    target_response,
    vulnerability_response,
)


def _paginated(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap records in the Snyk REST pagination envelope (no next page)."""
    return {"data": records, "links": {}}


class SnykMockTransportBuilder:
    """Builds a fake Snyk REST API transport.

    All Snyk REST endpoints return ``{"data": [...], "links": {}}``; an empty
    ``links`` object signals no next page so pagination stops after one call.

    The org-listing route uses a callable matcher (``r.url.path == "/rest/orgs"``)
    instead of a plain substring to avoid false-matching the more-specific
    ``/rest/orgs/{org_id}/...`` routes that share the same prefix.
    """

    def __init__(self) -> None:
        self._transport = InterceptTransport(strict=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_org_route(self) -> None:
        """Add the org-listing route using an exact-path callable matcher."""
        self._transport.add_route(
            "GET",
            lambda r: r.url.path == "/rest/orgs",
            {"status_code": 200, "json": _paginated([org_response()])},
        )

    def _add_org_table_route(
        self, table: str, records: list[dict[str, Any]]
    ) -> None:
        """Add a per-org table route: ``GET /rest/orgs/{org_id}/{table}``."""
        self._transport.add_route(
            "GET",
            f"/rest/orgs/{ORG_ID}/{table}",
            {"status_code": 200, "json": _paginated(records)},
        )

    # ------------------------------------------------------------------
    # Public builder methods (call table routes before org route)
    # ------------------------------------------------------------------

    def with_organization_routes(self) -> "SnykMockTransportBuilder":
        self._add_org_route()
        return self

    def with_project_routes(self) -> "SnykMockTransportBuilder":
        self._add_org_table_route(
            "projects",
            [project_response(i) for i in range(1, RECORD_COUNT + 1)],
        )
        self._add_org_route()
        return self

    def with_target_routes(self) -> "SnykMockTransportBuilder":
        self._add_org_table_route(
            "targets",
            [target_response(i) for i in range(1, RECORD_COUNT + 1)],
        )
        self._add_org_route()
        return self

    def with_vulnerability_routes(self) -> "SnykMockTransportBuilder":
        self._add_org_table_route(
            "issues",
            [vulnerability_response(i) for i in range(1, RECORD_COUNT + 1)],
        )
        self._add_org_route()
        return self

    def build(self, *, strict: bool = True) -> InterceptTransport:
        self._transport.strict = strict
        return self._transport
