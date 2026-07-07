import os
from typing import Any

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from expectations import KIND_EXPECTATIONS, KindExpectation
from helpers import integration_config, mapping_for_kind
from mocks.transport_builder import ServicenowMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

KIND_BLUEPRINTS: dict[str, str] = {
    "sys_user_group": "servicenowGroup",
    "sc_catalog": "servicenowCatalog",
    "incident": "servicenowIncident",
}

KIND_BUILDERS: dict[str, str] = {
    "sys_user_group": "with_user_group_routes",
    "sc_catalog": "with_service_catalog_routes",
    "incident": "with_incident_routes",
}

assert set(KIND_EXPECTATIONS) == set(
    KIND_BLUEPRINTS
), "KIND_EXPECTATIONS and KIND_BLUEPRINTS must cover the same kinds"


@pytest.mark.parametrize("kind", list(KIND_BLUEPRINTS))
@pytest.mark.asyncio
async def test_kind_resyncs(kind: str) -> None:
    builder = ServicenowMockTransportBuilder()
    getattr(builder, KIND_BUILDERS[kind])()
    transport = builder.build(strict=True)

    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_for_kind(kind),
        third_party_transport=transport,
        config_overrides=integration_config(),
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()
    finally:
        await harness.shutdown()

    _assert_kind_resync(result, kind)


def _assert_kind_resync(result: ResyncResult, kind: str) -> None:
    assert result.errors == [], f"Resync had errors for {kind}: {result.errors}"
    assert (
        result.reconciliation_success is True
    ), f"Reconciliation failed for {kind}: {result.errors}"

    blueprint = KIND_BLUEPRINTS[kind]
    entities = [e for e in result.upserted_entities if e["blueprint"] == blueprint]
    expectation = KIND_EXPECTATIONS[kind]

    _assert_entity_count(entities, expectation, kind, blueprint)
    _assert_entity_contents(entities, expectation, kind)


def _assert_entity_count(
    entities: list[dict[str, Any]],
    expectation: KindExpectation,
    kind: str,
    blueprint: str,
) -> None:
    assert len(entities) == expectation.count, (
        f"Expected {expectation.count} {blueprint} entities for kind {kind}, "
        f"got {len(entities)}: {[e['identifier'] for e in entities]}"
    )


def _assert_entity_contents(
    entities: list[dict[str, Any]],
    expectation: KindExpectation,
    kind: str,
) -> None:
    entities_by_id = {entity["identifier"]: entity for entity in entities}
    expected_ids = {expected.identifier for expected in expectation.entities}
    assert entities_by_id.keys() == expected_ids, (
        f"Unexpected identifiers for kind {kind}. "
        f"expected={sorted(expected_ids)} actual={sorted(entities_by_id)}"
    )
    for expected in expectation.entities:
        entity = entities_by_id[expected.identifier]
        if expected.title is not None:
            assert entity["title"] == expected.title, (
                f"{kind}/{expected.identifier} title mismatch: "
                f"expected {expected.title!r}, got {entity['title']!r}"
            )
        for key, value in expected.properties.items():
            assert entity["properties"].get(key) == value, (
                f"{kind}/{expected.identifier} property {key!r} mismatch: "
                f"expected {value!r}, got {entity['properties'].get(key)!r}"
            )
        for key, value in expected.relations.items():
            assert entity.get("relations", {}).get(key) == value, (
                f"{kind}/{expected.identifier} relation {key!r} mismatch: "
                f"expected {value!r}, got {entity.get('relations', {}).get(key)!r}"
            )
