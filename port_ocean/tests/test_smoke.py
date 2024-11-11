from os import environ
from typing import Tuple
import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.clients.port.types import UserAgentType
from port_ocean.tests.helpers.smoke_test import SmokeTestDetails


pytestmark = pytest.mark.smoke


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
async def test_valid_fake_integration(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
) -> None:
    _, port_client = port_client_for_fake_integration
    current_integration = await port_client.get_current_integration()
    assert current_integration is not None
    assert current_integration.get("resyncState") is not None
    assert current_integration.get("resyncState", {}).get("status") == "completed"


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
async def test_valid_fake_departments(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
) -> None:
    details, port_client = port_client_for_fake_integration
    entities = await port_client.search_entities(user_agent_type=UserAgentType.exporter)
    assert len(entities)
    departments = [
        x for x in entities if f"{x.blueprint}" == details.blueprint_department
    ]
    assert len(departments) == 5


@pytest.mark.skipif(
    environ.get("SMOKE_TEST_SUFFIX", None) is None,
    reason="You need to run the fake integration once",
)
async def test_valid_fake_persons(
    port_client_for_fake_integration: Tuple[SmokeTestDetails, PortClient],
) -> None:
    details, port_client = port_client_for_fake_integration
    headers = await port_client.auth.headers()
    fake_person_entities_result = await port_client.client.get(
        f"{port_client.auth.api_url}/blueprints/{details.blueprint_person}/entities",
        headers=headers,
    )

    fake_person_entities = fake_person_entities_result.json()["entities"]
    assert len(fake_person_entities)

    fake_departments_result = await port_client.client.get(
        f"{port_client.auth.api_url}/blueprints/{details.blueprint_department}/entities",
        headers=headers,
    )

    departments = [x["identifier"] for x in fake_departments_result.json()["entities"]]

    for department in departments:
        assert len(
            [
                x
                for x in fake_person_entities
                if x["relations"]["department"] == department
            ]
        )
