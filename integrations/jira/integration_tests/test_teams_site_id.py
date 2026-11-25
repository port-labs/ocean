import os

import pytest

from port_ocean.integration_testing import IntegrationTestHarness

from helpers import integration_config, mapping_for_kind
from mocks.payloads import SITE_ID, TEAM_COUNT, TEAMS_API_PATH, TENANT_INFO_URL
from mocks.transport_builder import JiraMockTransportBuilder

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))


@pytest.mark.asyncio
async def test_teams_requests_carry_the_site_id() -> None:
    """Atlassian rejects Teams calls without ``siteId``; make sure we always send it.

    The site ID is resolved from the public tenant_info endpoint, without
    sending the Jira credentials.
    """
    transport = JiraMockTransportBuilder().with_team_routes().build(strict=True)
    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_for_kind("team"),
        third_party_transport=transport,
        config_overrides=integration_config(),
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()
    finally:
        await harness.shutdown()

    assert result.errors == [], f"Resync had errors: {result.errors}"

    teams_calls = transport.calls_for(TEAMS_API_PATH)
    list_calls = [c for c in teams_calls if c.request.method == "GET"]
    member_calls = [c for c in teams_calls if c.request.method == "POST"]
    assert len(list_calls) == 1
    assert len(member_calls) == TEAM_COUNT
    for call in teams_calls:
        assert call.request.url.params.get("siteId") == SITE_ID
        assert call.response.status_code == 200

    tenant_info_calls = transport.calls_for(TENANT_INFO_URL)
    assert len(tenant_info_calls) == 1, "the site ID must be resolved once and cached"
    assert "authorization" not in tenant_info_calls[0].request.headers
