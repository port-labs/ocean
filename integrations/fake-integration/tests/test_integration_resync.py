"""Integration test that runs a full resync of the fake-integration
with controlled third-party and Port API responses.

This validates the entire pipeline:
  third-party API → on_resync handler → JQ transformation → Port upsert
"""

import os
from typing import Any

import pytest

from port_ocean.tests.integration import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)


class TestFakeIntegrationResync(BaseIntegrationTest):
    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

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
                                "properties": {
                                    "name": ".name",
                                },
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
        assert len(resync.upserted_entities) > 0, (
            f"Expected entities to be upserted, got none. Errors: {resync.errors}"
        )

        # Check departments were created
        department_entities = [
            e for e in resync.upserted_entities
            if e.get("blueprint") == "fakeDepartment"
        ]
        assert len(department_entities) > 0, "Expected department entities"
        assert department_entities[0]["identifier"] == "hr"
        assert department_entities[0]["properties"]["name"] == "hr"

        # Check persons were created
        person_entities = [
            e for e in resync.upserted_entities
            if e.get("blueprint") == "fakePerson"
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

    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

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
            e for e in resync.upserted_entities
            if e.get("blueprint") == "fakePerson"
        ]

        # Only Alice (WORKING) should pass, Bob (NOPE) should be filtered
        assert len(person_entities) == 1
        assert person_entities[0]["identifier"] == "person-1"
        assert person_entities[0]["properties"]["status"] == "WORKING"


class TestFakeIntegrationErrorHandling(BaseIntegrationTest):
    """Test that the integration handles third-party API errors gracefully."""

    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

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
            e for e in resync.upserted_entities
            if e.get("blueprint") == "fakeDepartment"
        ]
        assert len(department_entities) > 0

        # Person API returned 500, so no person entities should be upserted
        person_entities = [
            e for e in resync.upserted_entities
            if e.get("blueprint") == "fakePerson"
        ]
        assert len(person_entities) == 0
