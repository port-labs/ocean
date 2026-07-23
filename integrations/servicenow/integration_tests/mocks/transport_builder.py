from collections.abc import Callable
from typing import Any

from port_ocean.integration_testing import InterceptTransport

from mocks.payloads import (
    RECORD_COUNT,
    incident_response,
    service_catalog_response,
    user_group_response,
)


class ServicenowMockTransportBuilder:
    """Builds a fake ServiceNow Table API transport.

    Each ServiceNow resync fetches ``GET /api/now/table/{table}`` and reads the
    ``result`` array. Pagination stops when the response has no ``Link`` header
    with ``rel="next"``, so a single page per table is enough for the happy path.
    """

    def __init__(self) -> None:
        self._transport = InterceptTransport(strict=True)

    def _add_table_route(
        self,
        table: str,
        response_for_index: Callable[[int], dict[str, Any]],
    ) -> None:
        records = [response_for_index(i) for i in range(1, RECORD_COUNT + 1)]
        self._transport.add_route(
            "GET",
            f"/api/now/table/{table}",
            {"status_code": 200, "json": {"result": records}},
        )

    def with_user_group_routes(self) -> "ServicenowMockTransportBuilder":
        self._add_table_route("sys_user_group", user_group_response)
        return self

    def with_service_catalog_routes(self) -> "ServicenowMockTransportBuilder":
        self._add_table_route("sc_catalog", service_catalog_response)
        return self

    def with_incident_routes(self) -> "ServicenowMockTransportBuilder":
        self._add_table_route("incident", incident_response)
        return self

    def build(self, *, strict: bool = True) -> InterceptTransport:
        self._transport.strict = strict
        return self._transport
