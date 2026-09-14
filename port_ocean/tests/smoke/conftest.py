from collections.abc import AsyncGenerator
from typing import Tuple

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.smoke.helpers.actions import (
    ActionResources,
    cleanup_action_resources,
    setup_action_resources,
)
from port_ocean.tests.smoke.helpers.details import SmokeTestDetails
from port_ocean.tests.smoke.helpers.port_client import (
    get_port_client_for_fake_integration,
)


@pytest.fixture
def port_client_for_fake_integration() -> Tuple[SmokeTestDetails, PortClient]:
    from port_ocean.tests.smoke.helpers.details import get_smoke_test_details

    smoke_test_details = get_smoke_test_details()
    port_client = get_port_client_for_fake_integration()
    return smoke_test_details, port_client


@pytest.fixture
async def action_resources(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
) -> AsyncGenerator[ActionResources, None]:
    _, port_client = port_client_for_fake_integration
    resources = await setup_action_resources(port_client)
    try:
        yield resources
    finally:
        await cleanup_action_resources(port_client, resources)
