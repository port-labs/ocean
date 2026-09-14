from os import environ

from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.helpers.integration import cleanup_integration
from port_ocean.tests.helpers.port_client import get_port_client_for_integration
from port_ocean.tests.smoke.helpers.details import get_smoke_test_details


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
    return get_port_client_for_integration(
        client_id,
        client_secret,
        smoke_test_details.integration_identifier,
        smoke_test_details.integration_type,
        smoke_test_details.integration_version,
        base_url,
    )
