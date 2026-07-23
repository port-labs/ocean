from typing import Any

from port_ocean.integration_testing import BaseIntegrationTest, InterceptTransport
from port_ocean.integration_testing.harness import ResyncResult

from expectations import KIND_EXPECTATIONS
from helpers import full_mapping_config, integration_config
from mocks.transport_builder import PagerdutyMockTransportBuilder

# The full mapping has two incidents blocks (triggered+acknowledged and resolved),
# so incidents are upserted twice — the total count is 2 × RECORD_COUNT.
_INCIDENTS_BLUEPRINT = "pagerdutyIncident"
_INCIDENTS_MULTIPLIER = 2


class TestPagerDutyHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the PagerDuty integration.

    Exercises a full resync across all six default kinds at once:
    - services           → pagerdutyService entities
    - incidents (×2)     → pagerdutyIncident entities (two resource blocks)
    - schedules          → pagerdutySchedule entities
    - oncalls            → pagerdutyOncall entities
    - escalation_policies→ pagerdutyEscalationPolicy entities
    - users              → pagerdutyUser entities
    """

    def create_third_party_transport(self) -> InterceptTransport:
        return (
            PagerdutyMockTransportBuilder(strict=False)
            .with_services()
            .with_oncalls()
            .with_incidents()
            .with_schedules()
            .with_users()
            .with_escalation_policies()
            .build()
        )

    def create_mapping_config(self) -> dict[str, Any]:
        return full_mapping_config()

    def create_integration_config(self) -> dict[str, Any]:
        return integration_config()

    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert not resync.errors, f"Resync raised errors: {resync.errors}"

        by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for entity in resync.upserted_entities:
            by_blueprint.setdefault(entity["blueprint"], []).append(entity)

        for kind, expectation in KIND_EXPECTATIONS.items():
            blueprint = expectation.blueprint
            entities = by_blueprint.get(blueprint, [])

            # Incidents appear in two resource blocks, so double the expected count.
            expected_count = expectation.count
            if blueprint == _INCIDENTS_BLUEPRINT:
                expected_count *= _INCIDENTS_MULTIPLIER

            assert len(entities) == expected_count, (
                f"[{kind}] expected {expected_count} entities for blueprint "
                f"{blueprint!r}, got {len(entities)}"
            )

            for expected in expectation.entities:
                matching = [e for e in entities if e["identifier"] == expected.identifier]
                assert len(matching) >= 1, (
                    f"[{kind}] identifier {expected.identifier!r} not found"
                )
                entity = matching[0]
                if expected.title is not None:
                    assert entity.get("title") == expected.title, (
                        f"[{kind}] title mismatch for {expected.identifier!r}"
                    )
                for prop, value in expected.properties.items():
                    actual = entity.get("properties", {}).get(prop)
                    assert actual == value, (
                        f"[{kind}] property {prop!r} for {expected.identifier!r}: "
                        f"expected {value!r}, got {actual!r}"
                    )
                for rel, rel_value in expected.relations.items():
                    actual_rel = entity.get("relations", {}).get(rel)
                    assert actual_rel == rel_value, (
                        f"[{kind}] relation {rel!r} for {expected.identifier!r}: "
                        f"expected {rel_value!r}, got {actual_rel!r}"
                    )
