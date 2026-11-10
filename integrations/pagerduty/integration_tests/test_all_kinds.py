import os

import pytest

from port_ocean.integration_testing import IntegrationTestHarness, InterceptTransport

from expectations import KIND_EXPECTATIONS, assert_raw_items
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
    "services": ["with_oncalls"],  # update_oncall_users fetches /oncalls
    "schedules": ["with_users"],  # transform_user_ids_to_emails fetches /users
    "escalation_policies": ["with_oncalls"],  # attachOncallUsers fetches /oncalls
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

    assert not result.errors, f"[{kind}] resync raised errors: {result.errors}"
    assert {batch.kind for batch in result.raw_batches} == {
        kind
    }, f"[{kind}] unexpected kinds handed off: {result.raw_batches}"
    assert_raw_items(result.raw_items(kind), KIND_EXPECTATIONS[kind], kind)
