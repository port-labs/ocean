import os
from typing import Any

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, InterceptTransport

from expectations import KIND_EXPECTATIONS
from helpers import integration_config, mapping_for_kind
from mocks.transport_builder import PagerdutyMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Transport builder method name for each kind
_KIND_BUILDERS: dict[str, str] = {
    "services": "with_services",
    "incidents": "with_incidents",
    "schedules": "with_schedules",
    "oncalls": "with_oncalls",
    "escalation_policies": "with_escalation_policies",
    "users": "with_users",
}

# Some kinds need additional endpoints
_KIND_EXTRA_BUILDERS: dict[str, list[str]] = {
    "services": ["with_oncalls"],   # update_oncall_users fetches /oncalls
    "schedules": ["with_users"],    # transform_user_ids_to_emails fetches /users
}


def _transport_for_kind(kind: str) -> InterceptTransport:
    builder = PagerdutyMockTransportBuilder(strict=True)
    getattr(builder, _KIND_BUILDERS[kind])()
    for extra in _KIND_EXTRA_BUILDERS.get(kind, []):
        getattr(builder, extra)()
    return builder.build()


@pytest.mark.parametrize("kind", list(KIND_EXPECTATIONS.keys()))
@pytest.mark.asyncio
async def test_kind_resync(kind: str) -> None:
    expectation = KIND_EXPECTATIONS[kind]
    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_for_kind(kind),
        third_party_transport=_transport_for_kind(kind),
        config_overrides=integration_config(),
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()
    finally:
        await harness.shutdown()

    by_blueprint: dict[str, list[dict[str, Any]]] = {}
    for entity in result.upserted_entities:
        by_blueprint.setdefault(entity["blueprint"], []).append(entity)
    entities = by_blueprint.get(expectation.blueprint, [])

    assert len(entities) == expectation.count, (
        f"[{kind}] expected {expectation.count} entities, got {len(entities)}"
    )

    for expected in expectation.entities:
        matching = [e for e in entities if e["identifier"] == expected.identifier]
        assert len(matching) == 1, (
            f"[{kind}] identifier {expected.identifier!r} not found in upserted entities"
        )
        entity = matching[0]
        if expected.title is not None:
            assert entity.get("title") == expected.title, (
                f"[{kind}] title mismatch for {expected.identifier!r}"
            )
        for prop, value in expected.properties.items():
            actual = entity.get("properties", {}).get(prop)
            assert actual == value, (
                f"[{kind}] property {prop!r} mismatch for {expected.identifier!r}: "
                f"expected {value!r}, got {actual!r}"
            )
        for rel, rel_value in expected.relations.items():
            actual_rel = entity.get("relations", {}).get(rel)
            assert actual_rel == rel_value, (
                f"[{kind}] relation {rel!r} mismatch for {expected.identifier!r}: "
                f"expected {rel_value!r}, got {actual_rel!r}"
            )
