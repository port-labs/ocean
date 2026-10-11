from collections.abc import AsyncGenerator
from typing import Tuple

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.smoke.helpers.details import SmokeTestDetails
from port_ocean.tests.smoke.helpers.port_client import (
    get_port_client_for_fake_integration,
)
from port_ocean.tests.smoke.helpers.workflows import (
    WorkflowResources,
    cleanup_workflow_resources,
    new_workflow_resource_suffix,
    setup_workflow_resources,
)


@pytest.fixture
def port_client_for_fake_integration() -> Tuple[SmokeTestDetails, PortClient]:
    from port_ocean.tests.smoke.helpers.details import get_smoke_test_details

    smoke_test_details = get_smoke_test_details()
    port_client = get_port_client_for_fake_integration()
    return smoke_test_details, port_client


@pytest.fixture
async def workflow_resources(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
) -> AsyncGenerator[WorkflowResources, None]:
    _, port_client = port_client_for_fake_integration
    resources = await setup_workflow_resources(
        port_client, unique_suffix=new_workflow_resource_suffix()
    )
    try:
        yield resources
    finally:
        await cleanup_workflow_resources(port_client, resources)
