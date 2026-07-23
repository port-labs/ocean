import os
from typing import Any

import pytest
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)

from mocks.payloads import (
    RECORD_COUNT,
    SERVICENOW_PASSWORD,
    SERVICENOW_URL,
    SERVICENOW_USERNAME,
    created_on_iso,
    incident_response,
    service_catalog_response,
    sys_id,
    user_group_response,
)

_CREATED_ON = (
    '.sys_created_on | (strptime("%Y-%m-%d %H:%M:%S") | strftime("%Y-%m-%dT%H:%M:%SZ"))'
)
_SELECTOR: dict[str, Any] = {
    "query": "true",
    "apiQueryParams": {
        "sysparmDisplayValue": "true",
        "sysparmExcludeReferenceLink": "false",
    },
}


class TestServiceNowHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the ServiceNow integration.

    Exercises a full resync across all three default kinds at once:
    - sys_user_group  → servicenowGroup entities
    - sc_catalog      → servicenowCatalog entities
    - incident        → servicenowIncident entities

    Expected output: 2 entities per blueprint (RECORD_COUNT = 2),
    with titles, key properties, and the createdOn date-transform all verified.
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
        def _resource(kind: str, blueprint: str, mappings: dict[str, Any]) -> dict[str, Any]:
            return {
                "kind": kind,
                "selector": _SELECTOR,
                "port": {"entity": {"mappings": {"blueprint": f'"{blueprint}"', **mappings}}},
            }

        return {
            "resources": [
                _resource(
                    "sys_user_group",
                    "servicenowGroup",
                    {
                        "identifier": ".sys_id",
                        "title": ".name",
                        "properties": {
                            "description": ".description",
                            "isActive": ".active",
                            "createdOn": _CREATED_ON,
                            "createdBy": ".sys_created_by",
                        },
                    },
                ),
                _resource(
                    "sc_catalog",
                    "servicenowCatalog",
                    {
                        "identifier": ".sys_id",
                        "title": ".title",
                        "properties": {
                            "description": ".description",
                            "isActive": ".active",
                            "createdOn": _CREATED_ON,
                            "createdBy": ".sys_created_by",
                        },
                    },
                ),
                _resource(
                    "incident",
                    "servicenowIncident",
                    {
                        "identifier": ".sys_id",
                        "title": ".short_description",
                        "properties": {
                            "number": ".number | tostring",
                            "state": ".state",
                            "category": ".category",
                            "reopenCount": ".reopen_count",
                            "severity": ".severity",
                            "assignedTo": ".assigned_to.link",
                            "urgency": ".urgency",
                            "contactType": ".contact_type",
                            "createdOn": _CREATED_ON,
                            "createdBy": ".sys_created_by",
                            "isActive": ".active",
                            "priority": ".priority",
                        },
                    },
                ),
            ]
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-servicenow",
                "type": "servicenow",
                "config": {
                    "servicenow_url": SERVICENOW_URL,
                    "servicenow_username": SERVICENOW_USERNAME,
                    "servicenow_password": SERVICENOW_PASSWORD,
                    "enable_tables_live_events_webhooks": False,
                },
            }
        }

    @pytest.mark.asyncio
    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert resync.errors == [], f"Resync had errors: {resync.errors}"
        assert resync.reconciliation_success is True

        by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for entity in resync.upserted_entities:
            by_blueprint.setdefault(entity["blueprint"], []).append(entity)

        # --- Groups ---
        groups = by_blueprint.get("servicenowGroup", [])
        assert len(groups) == RECORD_COUNT, f"Expected {RECORD_COUNT} groups, got {len(groups)}"
        groups_by_id = {e["identifier"]: e for e in groups}
        for i in range(1, RECORD_COUNT + 1):
            record = user_group_response(i)
            entity = groups_by_id[sys_id("group", i)]
            assert entity["title"] == record["name"]
            assert entity["properties"]["description"] == record["description"]
            assert entity["properties"]["isActive"] == record["active"]
            assert entity["properties"]["createdOn"] == created_on_iso(i)
            assert entity["properties"]["createdBy"] == record["sys_created_by"]

        # --- Catalogs ---
        catalogs = by_blueprint.get("servicenowCatalog", [])
        assert len(catalogs) == RECORD_COUNT, f"Expected {RECORD_COUNT} catalogs, got {len(catalogs)}"
        catalogs_by_id = {e["identifier"]: e for e in catalogs}
        for i in range(1, RECORD_COUNT + 1):
            record = service_catalog_response(i)
            entity = catalogs_by_id[sys_id("catalog", i)]
            assert entity["title"] == record["title"]
            assert entity["properties"]["description"] == record["description"]
            assert entity["properties"]["isActive"] == record["active"]
            assert entity["properties"]["createdOn"] == created_on_iso(i)
            assert entity["properties"]["createdBy"] == record["sys_created_by"]

        # --- Incidents ---
        incidents = by_blueprint.get("servicenowIncident", [])
        assert len(incidents) == RECORD_COUNT, f"Expected {RECORD_COUNT} incidents, got {len(incidents)}"
        incidents_by_id = {e["identifier"]: e for e in incidents}
        for i in range(1, RECORD_COUNT + 1):
            record = incident_response(i)
            entity = incidents_by_id[sys_id("incident", i)]
            assert entity["title"] == record["short_description"]
            props = entity["properties"]
            assert props["number"] == record["number"]
            assert props["state"] == record["state"]
            assert props["category"] == record["category"]
            assert props["severity"] == record["severity"]
            assert props["assignedTo"] == record["assigned_to"]["link"]
            assert props["urgency"] == record["urgency"]
            assert props["contactType"] == record["contact_type"]
            assert props["createdOn"] == created_on_iso(i)
            assert props["isActive"] == record["active"]
            assert props["priority"] == record["priority"]
