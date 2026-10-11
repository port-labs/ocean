import asyncio
from os import environ
from time import monotonic

import httpx
from loguru import logger

from port_ocean.clients.port.client import PortClient
from port_ocean.tests.helpers.integration import cleanup_integration
from port_ocean.tests.helpers.port_client import get_port_client_for_integration
from port_ocean.tests.smoke.helpers.details import get_smoke_test_details


async def cleanup_smoke_test() -> None:
    smoke_test_details = get_smoke_test_details()
    client = get_port_client_for_fake_integration()

    logger.info("Cleaning up fake integration")
    await cleanup_integration(
        client,
        [smoke_test_details.blueprint_department, smoke_test_details.blueprint_person],
    )
    logger.info("Cleaning up fake integration complete")


async def wait_for_resync_completed(timeout_seconds: float = 180) -> None:
    client = get_port_client_for_fake_integration()
    deadline = monotonic() + timeout_seconds
    last_status = "missing"
    while monotonic() < deadline:
        try:
            integration = await client.get_current_integration(should_log=False)
        except httpx.HTTPError:
            integration = {}
        resync_state = integration.get("resyncState") or {}
        last_status = resync_state.get("status") or "missing"
        if last_status == "completed":
            logger.info("Smoke resync completed")
            return
        if last_status in {"failed", "aborted"}:
            raise RuntimeError(f"Smoke resync ended with status {last_status}")
        await asyncio.sleep(2)
    raise TimeoutError(
        f"Smoke resync did not complete within {timeout_seconds}s (last status: {last_status})"
    )


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
