"""Integration test that runs a full resync of the fake-integration
with controlled third-party and Port API responses.

This validates the entire pipeline:
  third-party API → on_resync handler → JQ transformation → Port upsert
"""

import os
import pytest

from port_ocean.tests.integration import (
    InterceptTransport,
    IntegrationTestHarness,
)


INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


# --- Fixtures ---


@pytest.fixture
def third_party_transport() -> InterceptTransport:
    """Mock the fake-integration's third-party API (localhost:8000).

    The fake-integration calls:
      GET http://localhost:8000/integration/department/{dept_id}/employees?limit=...
    for each department, and returns person data.
    """
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


@pytest.fixture
def mapping_config() -> dict:
    """Port mapping configuration: defines how raw data maps to Port entities."""
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


@pytest.fixture
def integration_config() -> dict:
    """Integration-specific config overrides."""
    return {
        "integration": {
            "identifier": "test-fake-integration",
            "type": "fake-integration",
            "config": {
                "single_department_run": True,
            },
        },
    }


# --- Tests ---


@pytest.mark.asyncio
async def test_resync_departments_and_persons(
    third_party_transport: InterceptTransport,
    mapping_config: dict,
    integration_config: dict,
) -> None:
    """Test a full resync produces the expected entities from controlled data."""
    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_config,
        third_party_transport=third_party_transport,
        config_overrides=integration_config,
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()

        # We should have entities upserted to Port
        assert len(result.upserted_entities) > 0, (
            f"Expected entities to be upserted, got none. Errors: {result.errors}"
        )

        # Check departments were created
        department_entities = [
            e for e in result.upserted_entities
            if e.get("blueprint") == "fakeDepartment"
        ]
        assert len(department_entities) > 0, "Expected department entities"

        # With single_department_run=True, we get 1 department ("hr")
        assert department_entities[0]["identifier"] == "hr"
        assert department_entities[0]["properties"]["name"] == "hr"

        # Check persons were created
        person_entities = [
            e for e in result.upserted_entities
            if e.get("blueprint") == "fakePerson"
        ]
        assert len(person_entities) > 0, "Expected person entities"

        # Verify person properties were mapped correctly
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

    finally:
        await harness.shutdown()


@pytest.mark.asyncio
async def test_resync_with_selector_filter(
    third_party_transport: InterceptTransport,
    integration_config: dict,
) -> None:
    """Test that JQ selectors correctly filter entities."""
    # Only allow persons with status == "WORKING"
    mapping_config = {
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

    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_config,
        third_party_transport=third_party_transport,
        config_overrides=integration_config,
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()

        person_entities = [
            e for e in result.upserted_entities
            if e.get("blueprint") == "fakePerson"
        ]

        # Only Alice (WORKING) should pass, Bob (NOPE) should be filtered
        assert len(person_entities) == 1
        assert person_entities[0]["identifier"] == "person-1"
        assert person_entities[0]["properties"]["status"] == "WORKING"

    finally:
        await harness.shutdown()


@pytest.mark.asyncio
async def test_third_party_error_handling(
    integration_config: dict,
    mapping_config: dict,
) -> None:
    """Test that the integration handles third-party API errors gracefully."""
    transport = InterceptTransport(strict=False)

    # Return 500 for person API calls
    transport.add_route(
        "GET",
        "localhost:8000/integration/department/",
        {"status_code": 500, "json": {"error": "Internal Server Error"}},
    )

    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_config,
        third_party_transport=transport,
        config_overrides=integration_config,
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()

        # Departments should still be created (they don't call the third-party API)
        department_entities = [
            e for e in result.upserted_entities
            if e.get("blueprint") == "fakeDepartment"
        ]
        assert len(department_entities) > 0

        # Person API returned 500, so no person entities should be upserted
        person_entities = [
            e for e in result.upserted_entities
            if e.get("blueprint") == "fakePerson"
        ]
        assert len(person_entities) == 0

    finally:
        await harness.shutdown()
