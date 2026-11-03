import os

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, ResyncResult

from expectations import KIND_EXPECTATIONS, assert_raw_items
from helpers import integration_config, mapping_for_kind
from mocks.transport_builder import ServicenowMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

KIND_BUILDERS: dict[str, str] = {
    "sys_user_group": "with_user_group_routes",
    "sc_catalog": "with_service_catalog_routes",
    "incident": "with_incident_routes",
}

assert set(KIND_EXPECTATIONS) == set(
    KIND_BUILDERS
), "KIND_EXPECTATIONS and KIND_BUILDERS must cover the same kinds"


@pytest.mark.parametrize("kind", list(KIND_BUILDERS))
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
    assert {batch.kind for batch in result.raw_batches} == {kind}

    assert_raw_items(result, kind, KIND_EXPECTATIONS[kind])
