import pytest
from unittest.mock import MagicMock, AsyncMock
from port_ocean.context.ocean import initialize_port_ocean_context, ocean
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from integration import (
    CloudCostResourceConfig,
    CloudCostSelector,
    OpencostResourceConfig,
    OpencostSelector,
)

# Test integration config
TEST_INTEGRATION_CONFIG = {
    "opencost_host": "http://localhost:9003",
}


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    """Mock the PortOcean context to prevent initialization errors."""

    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "opencost_host": TEST_INTEGRATION_CONFIG["opencost_host"],
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        mock_ocean_app.base_url = "https://baseurl.com"
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None

        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

    # Reset config to its original value to prevent test interference
    ocean.integration_config["opencost_host"] = TEST_INTEGRATION_CONFIG["opencost_host"]


@pytest.fixture
def cloudcost_resource_config() -> CloudCostResourceConfig:
    return CloudCostResourceConfig(
        kind="cloudcost",
        selector=CloudCostSelector(
            query="true", window="7d", aggregate=None, accumulate=None, filter=None
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".description",
                    blueprint='"cloudcost"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def opencost_resource_config() -> OpencostResourceConfig:
    return OpencostResourceConfig(
        kind="cost",
        selector=OpencostSelector(
            query="true", window="7d", aggregate=None, step=None, resolution=None
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".description",
                    blueprint='"cost"',
                    properties={},
                )
            )
        ),
    )
