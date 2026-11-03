from dataclasses import replace
from typing import Any

from port_ocean.integration_testing import BaseIntegrationTest, InterceptTransport
from port_ocean.integration_testing.harness import ResyncResult

from expectations import KIND_EXPECTATIONS, KindExpectation, assert_raw_items
from helpers import full_mapping_config, integration_config
from mocks.transport_builder import PagerdutyMockTransportBuilder

_INCIDENTS_KIND = "incidents"
# The full mapping has two incidents blocks (triggered+acknowledged and resolved),
# so each incident is extracted once per status.
_INCIDENT_STATUSES = {"triggered", "resolved"}


def _with_status(expectation: KindExpectation, status: str) -> KindExpectation:
    return replace(
        expectation,
        records=tuple(
            replace(record, fields={**record.fields, "status": status})
            for record in expectation.records
        ),
    )


class TestPagerDutyHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the PagerDuty integration.

    Exercises a full resync across all six default kinds at once and checks the
    raw items handed to Port for each kind (incidents come from two resource blocks).
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
        assert {batch.kind for batch in resync.raw_batches} == set(KIND_EXPECTATIONS)

        for kind, expectation in KIND_EXPECTATIONS.items():
            if kind != _INCIDENTS_KIND:
                assert_raw_items(resync.raw_items(kind), expectation, kind)

        incidents_by_status: dict[str, list[dict[str, Any]]] = {}
        for item in resync.raw_items(_INCIDENTS_KIND):
            incidents_by_status.setdefault(item["status"], []).append(item)
        assert incidents_by_status.keys() == _INCIDENT_STATUSES
        for status, items in incidents_by_status.items():
            assert_raw_items(
                items,
                _with_status(KIND_EXPECTATIONS[_INCIDENTS_KIND], status),
                f"{_INCIDENTS_KIND}[{status}]",
            )
