import os
from typing import Any

import pytest
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)

from helpers import all_mappings, integration_config
from mocks.payloads import (
    RECORD_COUNT,
    created_on,
    incident_response,
    service_catalog_response,
    sys_id,
    user_group_response,
)


class TestServiceNowHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the ServiceNow integration.

    Exercises a full resync across all three default kinds at once:
    - sys_user_group  → raw group records
    - sc_catalog      → raw catalog records
    - incident        → raw incident records

    Expected output: 2 raw records per kind (RECORD_COUNT = 2) handed off to
    Port, each located by `sys_id` with the raw fields the mapping reads verified.
    """

    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        t = InterceptTransport(strict=True)

        def _table_route(table: str, records: list[dict[str, Any]]) -> None:
            t.add_route(
                "GET",
                f"/api/now/table/{table}",
                {"status_code": 200, "json": {"result": records}},
            )

        _table_route(
            "sys_user_group",
            [user_group_response(i) for i in range(1, RECORD_COUNT + 1)],
        )
        _table_route(
            "sc_catalog",
            [service_catalog_response(i) for i in range(1, RECORD_COUNT + 1)],
        )
        _table_route(
            "incident",
            [incident_response(i) for i in range(1, RECORD_COUNT + 1)],
        )

        return t

    def create_mapping_config(self) -> dict[str, Any]:
        return all_mappings()

    def create_integration_config(self) -> dict[str, Any]:
        return integration_config()

    @pytest.mark.asyncio
    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert resync.errors == [], f"Resync had errors: {resync.errors}"
        assert resync.reconciliation_success is True

        # --- Groups ---
        groups = resync.raw_items("sys_user_group")
        assert (
            len(groups) == RECORD_COUNT
        ), f"Expected {RECORD_COUNT} groups, got {len(groups)}"
        groups_by_id = {g["sys_id"]: g for g in groups}
        for i in range(1, RECORD_COUNT + 1):
            record = user_group_response(i)
            group = groups_by_id[sys_id("group", i)]
            assert group["name"] == record["name"]
            assert group["description"] == record["description"]
            assert group["active"] == record["active"]
            assert group["sys_created_on"] == created_on(i)
            assert group["sys_created_by"] == record["sys_created_by"]

        # --- Catalogs ---
        catalogs = resync.raw_items("sc_catalog")
        assert (
            len(catalogs) == RECORD_COUNT
        ), f"Expected {RECORD_COUNT} catalogs, got {len(catalogs)}"
        catalogs_by_id = {c["sys_id"]: c for c in catalogs}
        for i in range(1, RECORD_COUNT + 1):
            record = service_catalog_response(i)
            catalog = catalogs_by_id[sys_id("catalog", i)]
            assert catalog["title"] == record["title"]
            assert catalog["description"] == record["description"]
            assert catalog["active"] == record["active"]
            assert catalog["sys_created_on"] == created_on(i)
            assert catalog["sys_created_by"] == record["sys_created_by"]

        # --- Incidents ---
        incidents = resync.raw_items("incident")
        assert (
            len(incidents) == RECORD_COUNT
        ), f"Expected {RECORD_COUNT} incidents, got {len(incidents)}"
        incidents_by_id = {inc["sys_id"]: inc for inc in incidents}
        for i in range(1, RECORD_COUNT + 1):
            record = incident_response(i)
            incident = incidents_by_id[sys_id("incident", i)]
            assert incident["short_description"] == record["short_description"]
            assert incident["number"] == record["number"]
            assert incident["state"] == record["state"]
            assert incident["category"] == record["category"]
            assert incident["reopen_count"] == record["reopen_count"]
            assert incident["severity"] == record["severity"]
            assert incident["assigned_to"]["link"] == record["assigned_to"]["link"]
            assert incident["urgency"] == record["urgency"]
            assert incident["contact_type"] == record["contact_type"]
            assert incident["sys_created_on"] == created_on(i)
            assert incident["sys_created_by"] == record["sys_created_by"]
            assert incident["active"] == record["active"]
            assert incident["priority"] == record["priority"]
