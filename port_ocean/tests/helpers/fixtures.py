from os import environ, path
from typing import Any, AsyncGenerator, Callable, List, Tuple, Union

import pytest_asyncio
from pydantic import BaseModel

from port_ocean.clients.port.client import PortClient
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.ocean import Ocean
from port_ocean.tests.helpers.ocean_app import (
    get_integation_resource_configs,
    get_integration_ocean_app,
)


def get_port_client_for_integration(
    client_id: str,
    client_secret: str,
    integration_identifier: str,
    integration_type: str,
    integration_version: str,
    base_url: Union[str, None],
) -> PortClient:
    return PortClient(
        base_url=base_url or "https://api.getport/io",
        client_id=client_id,
        client_secret=client_secret,
        integration_identifier=integration_identifier,
        integration_type=integration_type,
        integration_version=integration_version,
    )


async def cleanup_integration(client: PortClient, blueprints: List[str]) -> None:
    for blueprint in blueprints:
        bp = await client.get_blueprint(blueprint)
        if bp is not None:
            migration_id = await client.delete_blueprint(
                identifier=blueprint, delete_entities=True
            )
            if migration_id:
                await client.wait_for_migration_to_complete(migration_id=migration_id)
    headers = await client.auth.headers()
    await client.client.delete(f"{client.auth.api_url}/integrations", headers=headers)


class SmokeTestDetails(BaseModel):
    integration_identifier: str
    blueprint_department: str
    blueprint_person: str


@pytest_asyncio.fixture()
async def port_client_for_fake_integration() -> (
    AsyncGenerator[Tuple[SmokeTestDetails, PortClient], None]
):
    blueprint_department = "fake-department"
    blueprint_person = "fake-person"
    integration_identifier = "smoke-test-integration"
    smoke_test_suffix = environ.get("SMOKE_TEST_SUFFIX")
    client_id = environ.get("PORT_CLIENT_ID")
    client_secret = environ.get("PORT_CLIENT_SECRET")

    if not client_secret or not client_id:
        assert False, "Missing port credentials"

    base_url = environ.get("PORT_BASE_URL")
    integration_version = "0.1.1-dev"
    integration_type = "smoke-test"
    if smoke_test_suffix is not None:
        integration_identifier = f"{integration_identifier}-{smoke_test_suffix}"
        blueprint_person = f"{blueprint_person}-{smoke_test_suffix}"
        blueprint_department = f"{blueprint_department}-{smoke_test_suffix}"

    client = get_port_client_for_integration(
        client_id,
        client_secret,
        integration_identifier,
        integration_type,
        integration_version,
        base_url,
    )

    smoke_test_details = SmokeTestDetails(
        integration_identifier=integration_identifier,
        blueprint_person=blueprint_person,
        blueprint_department=blueprint_department,
    )
    yield smoke_test_details, client
    await cleanup_integration(client, [blueprint_department, blueprint_person])


@pytest_asyncio.fixture
def get_mocked_ocean_app(request: Any) -> Callable[[], Ocean]:
    test_dir = path.join(path.dirname(request.module.__file__), "..")

    def get_ocean_app() -> Ocean:
        return get_integration_ocean_app(test_dir)

    return get_ocean_app


@pytest_asyncio.fixture
def get_mock_ocean_resource_configs(request: Any) -> Callable[[], List[ResourceConfig]]:
    module_dir = path.join(path.dirname(request.module.__file__), "..")

    def get_ocean_resource_configs() -> List[ResourceConfig]:
        return get_integation_resource_configs(module_dir)

    return get_ocean_resource_configs
