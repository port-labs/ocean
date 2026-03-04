"""Integration test that runs a full resync of the fake-integration
with controlled third-party and Port API responses.

This validates the entire pipeline:
  third-party API → on_resync handler → JQ transformation → Port upsert
"""

from typing import Any

import pytest

from port_ocean.tests.integration import (
    BaseIntegrationTest,
    InterceptTransport,
    IntegrationTestHarness,
    ResyncResult,
)


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
        """Test a full resync produces the expected entities from controlled data."""
        assert (
            len(resync.upserted_entities) > 0
        ), f"Expected entities to be upserted, got none. Errors: {resync.errors}"

        # Check departments were created
        department_entities = [
            e
            for e in resync.upserted_entities
            if e.get("blueprint") == "fakeDepartment"
        ]
        assert len(department_entities) > 0, "Expected department entities"
        assert department_entities[0]["identifier"] == "hr"
        assert department_entities[0]["properties"]["name"] == "hr"

        # Check persons were created
        person_entities = [
            e for e in resync.upserted_entities if e.get("blueprint") == "fakePerson"
        ]
        assert len(person_entities) > 0, "Expected person entities"

        person_ids = {e["identifier"] for e in person_entities}
        assert "person-1" in person_ids
        assert "person-2" in person_ids

        # Check a specific person's mapped properties
        alice = next(e for e in person_entities if e["identifier"] == "person-1")
        assert alice["title"] == "Alice Smith"
        assert alice["properties"]["email"] == "alice@test.com"
        assert alice["properties"]["age"] == 30
        assert alice["properties"]["status"] == "WORKING"
        assert alice["relations"]["department"] == "hr"


class TestFakeIntegrationSelectorFilter(BaseIntegrationTest):
    """Test that JQ selectors correctly filter entities."""

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
    async def test_only_working_persons_pass(self, resync: ResyncResult) -> None:
        person_entities = [
            e for e in resync.upserted_entities if e.get("blueprint") == "fakePerson"
        ]

        # Only Alice (WORKING) should pass, Bob (NOPE) should be filtered
        assert len(person_entities) == 1
        assert person_entities[0]["identifier"] == "person-1"
        assert person_entities[0]["properties"]["status"] == "WORKING"


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
        # Departments should still be created (they don't call the third-party API)
        department_entities = [
            e
            for e in resync.upserted_entities
            if e.get("blueprint") == "fakeDepartment"
        ]
        assert len(department_entities) > 0

        # Person API returned 500, so no person entities should be upserted
        # The error should be caught and added to resync.errors
        person_entities = [
            e for e in resync.upserted_entities if e.get("blueprint") == "fakePerson"
        ]
        assert len(person_entities) == 0

        # The resync should have encountered an HTTP error
        assert len(resync.errors) > 0, (
            f"Expected resync to encounter an HTTP error, but got: {resync.errors}. "
            f"The fake-integration should raise HTTPStatusError when the API returns 500."
        )

        # Extract all exceptions, recursively unwrapping ExceptionGroups
        def extract_exceptions(errors: list[Exception]) -> list[Exception]:
            """Recursively extract exceptions from ExceptionGroups."""
            result = []
            for error in errors:
                if isinstance(error, ExceptionGroup) and hasattr(error, "exceptions"):
                    result.extend(extract_exceptions(list(error.exceptions)))
                else:
                    result.append(error)
            return result

        all_errors = extract_exceptions(resync.errors)

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
    """Test that entities are properly deleted when they no longer exist in the source."""

    def create_third_party_transport(self) -> InterceptTransport:
        """Mock returns only person-1 (person-2 and person-3 will be deleted)."""
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
        """Entities that 'exist in Port' — will be deleted since they're not in new resync."""
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
    async def test_deleted_entities_are_captured(
        self, harness: IntegrationTestHarness
    ) -> None:
        """Test that entities existing in Port but not in the new resync are deleted."""
        # Trigger resync - person-1 will be created, person-2 and person-3 will be deleted
        result = await harness.trigger_resync()

        # Verify reconciliation succeeded
        assert (
            result.reconciliation_success is True
        ), f"Reconciliation should succeed, but got errors: {result.errors}"

        # Verify person-1 was upserted
        person_entities = [
            e for e in result.upserted_entities if e.get("blueprint") == "fakePerson"
        ]
        assert len(person_entities) == 1
        assert person_entities[0]["identifier"] == "person-1"

        # Verify person-2 and person-3 were deleted
        assert (
            len(result.deleted_entities) >= 2
        ), f"Expected at least 2 deleted entities, got: {result.deleted_entities}"

        deleted_identifiers = {e["identifier"] for e in result.deleted_entities}
        assert (
            "person-2" in deleted_identifiers
        ), f"Expected person-2 to be deleted, but deleted entities are: {deleted_identifiers}"
        assert (
            "person-3" in deleted_identifiers
        ), f"Expected person-3 to be deleted, but deleted entities are: {deleted_identifiers}"

        # Verify deleted entities have the correct structure
        person_2_deleted = next(
            e for e in result.deleted_entities if e["identifier"] == "person-2"
        )
        assert person_2_deleted["blueprint"] == "fakePerson"
        assert person_2_deleted["identifier"] == "person-2"
