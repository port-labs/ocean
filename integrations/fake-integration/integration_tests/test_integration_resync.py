"""Integration test that runs a full resync of the fake-integration
with controlled third-party and Port API responses.

This validates Ocean's side of the pipeline:
  third-party API → on_resync handler → raw items handed to the data-source-processor

Mapping, selector filtering and stale-entity reconciliation happen in the
data-source-processor, driven by the lifecycle API calls Ocean makes.
"""

from typing import Any

import pytest

from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    IntegrationTestHarness,
    ResyncResult,
)
from port_ocean.integration_testing.port_mock import LifecycleCall


def resync_lifecycle_calls(result: ResyncResult) -> list[LifecycleCall]:
    """Resync-level lifecycle calls (POST /v1/lifecycle/{resync_id})."""
    return [
        call
        for call in result.lifecycle_calls
        if call.method == "POST"
        and call.body is not None
        and len(call.path.strip("/").split("/")) == 3
    ]


def kind_lifecycle_statuses(result: ResyncResult) -> dict[str, list[str]]:
    """Statuses reported per kind identifier (POST /v1/lifecycle/{resync_id}/kind)."""
    statuses: dict[str, list[str]] = {}
    for call in result.lifecycle_calls:
        if call.method == "POST" and call.path.endswith("/kind") and call.body:
            statuses.setdefault(call.body["kind_identifier"], []).append(
                call.body["status"]
            )
    return statuses


def resync_statuses(result: ResyncResult) -> list[str]:
    return [call.body["status"] for call in resync_lifecycle_calls(result) if call.body]


class TestFakeIntegrationResync(BaseIntegrationTest):
    def create_third_party_transport(self) -> InterceptTransport:
        """Mock the fake-integration's third-party API (localhost:8000)."""
        transport = InterceptTransport(strict=False)

        transport.add_route(
            "GET",
            "localhost:8000/integration/department/",
            {
                "json": {
                    "results": [
                        {
                            "id": "person-1",
                            "email": "alice@test.com",
                            "name": "Alice Smith",
                            "status": "WORKING",
                            "age": 30,
                            "bio": "Engineer",
                        },
                        {
                            "id": "person-2",
                            "email": "bob@test.com",
                            "name": "Bob Jones",
                            "status": "NOPE",
                            "age": 25,
                            "bio": "Designer",
                        },
                    ]
                }
            },
        )

        return transport

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "enableMergeEntity": True,
            "resources": [
                {
                    "kind": "fake-department",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakeDepartment"',
                                "properties": {"name": ".name"},
                            }
                        }
                    },
                },
                {
                    "kind": "fake-person",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakePerson"',
                                "properties": {
                                    "email": ".email",
                                    "age": ".age",
                                    "status": ".status",
                                },
                                "relations": {
                                    "department": ".department.id",
                                },
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-fake-integration",
                "type": "fake-integration",
                "config": {
                    "single_department_run": True,
                },
            },
        }

    @pytest.mark.asyncio
    async def test_resync_departments_and_persons(self, resync: ResyncResult) -> None:
        """Test a full resync hands the expected raw items to the data-source-processor."""
        assert not resync.errors, f"Unexpected resync errors: {resync.errors}"
        assert resync.upserted_entities == []

        departments = resync.raw_items("fake-department")
        assert len(departments) > 0, "Expected raw department items"
        assert departments[0]["id"] == "hr"
        assert departments[0]["name"] == "hr"

        persons = resync.raw_items("fake-person")
        assert {p["id"] for p in persons} == {"person-1", "person-2"}

        alice = next(p for p in persons if p["id"] == "person-1")
        assert alice["name"] == "Alice Smith"
        assert alice["email"] == "alice@test.com"
        assert alice["age"] == 30
        assert alice["status"] == "WORKING"
        assert alice["department"]["id"] == "hr"

        assert resync_statuses(resync) == ["started", "finished"]


class TestFakeIntegrationSelectorFilter(BaseIntegrationTest):
    """Test that selectors are forwarded to the data-source-processor, which filters."""

    def create_third_party_transport(self) -> InterceptTransport:
        transport = InterceptTransport(strict=False)
        transport.add_route(
            "GET",
            "localhost:8000/integration/department/",
            {
                "json": {
                    "results": [
                        {
                            "id": "person-1",
                            "email": "alice@test.com",
                            "name": "Alice Smith",
                            "status": "WORKING",
                            "age": 30,
                            "bio": "Engineer",
                        },
                        {
                            "id": "person-2",
                            "email": "bob@test.com",
                            "name": "Bob Jones",
                            "status": "NOPE",
                            "age": 25,
                            "bio": "Designer",
                        },
                    ]
                }
            },
        )
        return transport

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "enableMergeEntity": True,
            "resources": [
                {
                    "kind": "fake-department",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakeDepartment"',
                                "properties": {"name": ".name"},
                            }
                        }
                    },
                },
                {
                    "kind": "fake-person",
                    "selector": {"query": '.status == "WORKING"'},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakePerson"',
                                "properties": {
                                    "email": ".email",
                                    "status": ".status",
                                },
                                "relations": {},
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-fake-integration",
                "type": "fake-integration",
                "config": {
                    "single_department_run": True,
                },
            },
        }

    @pytest.mark.asyncio
    async def test_all_persons_handed_off_with_selector_query(
        self, resync: ResyncResult
    ) -> None:
        assert not resync.errors, f"Unexpected resync errors: {resync.errors}"

        # Ocean no longer filters: both Alice (WORKING) and Bob (NOPE) are handed off
        persons = resync.raw_items("fake-person")
        assert {p["id"]: p["status"] for p in persons} == {
            "person-1": "WORKING",
            "person-2": "NOPE",
        }

        # The selector query reaches the data-source-processor via the resync mapping
        started = [
            call.body
            for call in resync_lifecycle_calls(resync)
            if call.body and call.body["status"] == "started"
        ]
        assert len(started) == 1
        resources = started[0]["mapping"]["resources"]
        person_resource = next(r for r in resources if r["kind"] == "fake-person")
        assert person_resource["selector"]["query"] == '.status == "WORKING"'


class TestFakeIntegrationErrorHandling(BaseIntegrationTest):
    """Test that the integration handles third-party API errors gracefully."""

    def create_third_party_transport(self) -> InterceptTransport:
        transport = InterceptTransport(strict=False)
        # Return 500 for person API calls
        transport.add_route(
            "GET",
            "localhost:8000/integration/department/",
            {"status_code": 500, "json": {"error": "Internal Server Error"}},
        )
        return transport

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "enableMergeEntity": True,
            "resources": [
                {
                    "kind": "fake-department",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakeDepartment"',
                                "properties": {"name": ".name"},
                            }
                        }
                    },
                },
                {
                    "kind": "fake-person",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakePerson"',
                                "properties": {
                                    "email": ".email",
                                    "age": ".age",
                                    "status": ".status",
                                },
                                "relations": {
                                    "department": ".department.id",
                                },
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-fake-integration",
                "type": "fake-integration",
                "config": {
                    "single_department_run": True,
                },
            },
        }

    @pytest.mark.asyncio
    async def test_no_persons_on_api_error(self, resync: ResyncResult) -> None:
        # Departments are still handed off (they don't call the third-party API)
        departments = resync.raw_items("fake-department")
        assert [d["id"] for d in departments] == ["hr"]

        # Person API returned 500, so no raw person items are handed off
        assert resync.raw_items("fake-person", operation=None) == []
        assert resync.reconciliation_success is False

        # The failed kind is reported to the lifecycle API; the healthy kind finishes
        kind_statuses = kind_lifecycle_statuses(resync)
        assert kind_statuses["fake-department-0"] == ["started", "finished"]
        assert kind_statuses["fake-person-1"] == ["started", "failed"]

        # A partial resync is reported as failed so stale entities are not reconciled away
        assert resync_statuses(resync) == ["started", "failed"]

        # The resync should have encountered an HTTP error
        assert len(resync.errors) > 0, (
            f"Expected resync to encounter an HTTP error, but got: {resync.errors}. "
            f"The fake-integration should raise HTTPStatusError when the API returns 500."
        )

        # Extract all exceptions, recursively unwrapping ExceptionGroups
        def extract_exceptions(errors: list[Exception]) -> list[Exception]:
            """Recursively extract exceptions from ExceptionGroups."""
            result: list[Exception] = []
            for error in errors:
                if isinstance(error, ExceptionGroup) and hasattr(error, "exceptions"):
                    result.extend(extract_exceptions(list(error.exceptions)))
                else:
                    result.append(error)
            return result

        all_errors: list[Exception] = extract_exceptions(resync.errors)

        # Verify at least one error is HTTP-related
        http_errors = [
            e
            for e in all_errors
            if any(
                keyword in str(e).lower()
                for keyword in ["500", "internal server error", "http", "httpx"]
            )
        ]
        assert (
            len(http_errors) > 0
        ), f"Expected at least one HTTP-related error, but got: {all_errors}"


class TestFakeIntegrationDeletions(BaseIntegrationTest):
    """Test that stale entities are left to the data-source-processor to reconcile."""

    def create_third_party_transport(self) -> InterceptTransport:
        """Mock returns only person-1 (person-2 and person-3 are stale in Port)."""
        transport = InterceptTransport(strict=False)
        transport.add_route(
            "GET",
            "localhost:8000/integration/department/",
            {
                "json": {
                    "results": [
                        {
                            "id": "person-1",
                            "email": "alice@test.com",
                            "name": "Alice Smith",
                            "status": "WORKING",
                            "age": 30,
                            "bio": "Engineer",
                        },
                    ]
                }
            },
        )
        return transport

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "enableMergeEntity": True,
            "entityDeletionThreshold": 1.0,  # Allow all deletions for testing
            "resources": [
                {
                    "kind": "fake-department",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakeDepartment"',
                                "properties": {"name": ".name"},
                            }
                        }
                    },
                },
                {
                    "kind": "fake-person",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"fakePerson"',
                                "properties": {
                                    "email": ".email",
                                    "age": ".age",
                                    "status": ".status",
                                },
                                "relations": {
                                    "department": ".department.id",
                                },
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-fake-integration",
                "type": "fake-integration",
                "config": {
                    "single_department_run": True,
                },
            },
        }

    def get_port_search_entities_response(self) -> list[dict[str, Any]]:
        """Entities that 'exist in Port' but are no longer returned by the source."""
        return [
            {
                "identifier": "person-2",
                "blueprint": "fakePerson",
                "title": "Bob Jones",
                "properties": {
                    "email": "bob@test.com",
                    "age": 25,
                    "status": "NOPE",
                },
                "relations": {
                    "department": "hr",
                },
            },
            {
                "identifier": "person-3",
                "blueprint": "fakePerson",
                "title": "Charlie Brown",
                "properties": {
                    "email": "charlie@test.com",
                    "age": 35,
                    "status": "WORKING",
                },
                "relations": {
                    "department": "hr",
                },
            },
        ]

    @pytest.mark.asyncio
    async def test_stale_entities_left_to_dsp_reconciliation(
        self, harness: IntegrationTestHarness
    ) -> None:
        """Ocean hands off only current items and signals resync completion; the
        data-source-processor deletes person-2 and person-3 when it reconciles."""
        result = await harness.trigger_resync()

        assert (
            result.reconciliation_success is True
        ), f"Resync should succeed, but got errors: {result.errors}"

        persons = result.raw_items("fake-person")
        assert [p["id"] for p in persons] == ["person-1"]

        # Ocean itself neither deletes entities nor emits delete operations
        assert result.deleted_entities == []
        assert result.raw_items(operation="delete") == []

        # A finished resync is what lets the data-source-processor reconcile stale entities
        assert resync_statuses(result) == ["started", "finished"]
        kind_statuses = kind_lifecycle_statuses(result)
        assert kind_statuses["fake-person-1"] == ["started", "finished"]
