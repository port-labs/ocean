from os import environ
from port_ocean.clients.port.client import PortClient

from loguru import logger
from pydantic import BaseModel

from port_ocean.tests.helpers.integration import cleanup_integration
from port_ocean.tests.helpers.port_client import get_port_client_for_integration


class SmokeTestDetails(BaseModel):
    integration_identifier: str
    blueprint_department: str
    blueprint_person: str
    integration_type: str
    integration_version: str


def get_smoke_test_details() -> SmokeTestDetails:
    blueprint_department = "fake-department"
    blueprint_person = "fake-person"
    integration_identifier = "smoke-test-integration"
    smoke_test_suffix = environ.get("SMOKE_TEST_SUFFIX")
    if smoke_test_suffix is not None:
        integration_identifier = f"{integration_identifier}-{smoke_test_suffix}"
        blueprint_person = f"{blueprint_person}-{smoke_test_suffix}"
        blueprint_department = f"{blueprint_department}-{smoke_test_suffix}"

    return SmokeTestDetails(
        integration_identifier=integration_identifier,
        blueprint_person=blueprint_person,
        blueprint_department=blueprint_department,
        integration_version="0.1.4-dev",
        integration_type="smoke-test",
    )


async def cleanup_smoke_test() -> None:
    smoke_test_details = get_smoke_test_details()
    client_id = environ.get("PORT_CLIENT_ID")
    client_secret = environ.get("PORT_CLIENT_SECRET")

    if not client_secret or not client_id:
        assert False, "Missing port credentials"

    base_url = environ.get("PORT_BASE_URL")
    client = get_port_client_for_integration(
        client_id,
        client_secret,
        smoke_test_details.integration_identifier,
        smoke_test_details.integration_type,
        smoke_test_details.integration_version,
        base_url,
    )

    logger.info("Cleaning up fake integration")
    await cleanup_integration(
        client,
        [smoke_test_details.blueprint_department, smoke_test_details.blueprint_person],
    )
    logger.info("Cleaning up fake integration complete")


def get_port_client_for_fake_integration() -> PortClient:
    smoke_test_details = get_smoke_test_details()
    client_id = environ.get("PORT_CLIENT_ID")
    client_secret = environ.get("PORT_CLIENT_SECRET")

    if not client_secret or not client_id:
        assert False, "Missing port credentials"

    base_url = environ.get("PORT_BASE_URL")
    client = get_port_client_for_integration(
        client_id,
        client_secret,
        smoke_test_details.integration_identifier,
        smoke_test_details.integration_type,
        smoke_test_details.integration_version,
        base_url,
    )

    return client
