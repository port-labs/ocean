from os import path
from typing import Any, Callable, Dict, List, Tuple, Union

import pytest

from port_ocean.clients.port.client import PortClient
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.ocean import Ocean
from port_ocean.tests.helpers.ocean_app import (
    get_integation_resource_configs,
    get_integration_ocean_app,
)
from port_ocean.tests.helpers.smoke_test import (
    SmokeTestDetails,
    get_port_client_for_fake_integration,
    get_smoke_test_details,
)


@pytest.fixture
def port_client_for_fake_integration() -> Tuple[SmokeTestDetails, PortClient]:
    smoke_test_details = get_smoke_test_details()
    port_client = get_port_client_for_fake_integration()

    return smoke_test_details, port_client


@pytest.fixture
def get_mocked_ocean_app(request: Any) -> Callable[[], Ocean]:
    test_dir = path.join(path.dirname(request.module.__file__), "..")

    def get_ocean_app(config_overrides: Union[Dict[str, Any], None] = None) -> Ocean:
        return get_integration_ocean_app(test_dir, config_overrides)

    return get_ocean_app


@pytest.fixture
def get_mock_ocean_resource_configs(request: Any) -> Callable[[], List[ResourceConfig]]:
    module_dir = path.join(path.dirname(request.module.__file__), "..")

    def get_ocean_resource_configs() -> List[ResourceConfig]:
        return get_integation_resource_configs(module_dir)

    return get_ocean_resource_configs
