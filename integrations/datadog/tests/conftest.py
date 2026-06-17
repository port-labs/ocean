from typing import Any, Generator

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datadog.client import DatadogClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError


@pytest.fixture(autouse=True)
def mock_client_manager() -> Generator[MagicMock, None, None]:
    """Patch the client manager at the point it is consumed so processor fixtures
    can be created without real Datadog credentials. By default the manager
    resolves any payload to a single mock client."""
    manager = MagicMock()
    manager.clients = [MagicMock()]
    manager.get_client_by_org_uuid.return_value = MagicMock()
    with patch(
        "datadog.webhook.webhook_processors.base_webhook_processor.get_client_manager",
        return_value=manager,
    ):
        yield manager


@pytest.fixture(autouse=True)
def mock_integration_config() -> Generator[dict[str, Any], None, None]:
    """Mock the ocean integration config."""
    config: dict[str, Any] = {
        "datadog_service_dependency_env": "prod",
        "webhook_secret": "test_token",
        "is_multi_org": False,
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture(autouse=True)
def mock_integration_config_without_webhook_secret() -> (
    Generator[dict[str, Any], None, None]
):
    """Mock the ocean integration config."""
    config: dict[str, Any] = {
        "datadog_service_dependency_env": "prod",
        "is_multi_org": False,
    }
    with patch(
        "port_ocean.context.ocean.PortOceanContext.integration_config",
        new_callable=PropertyMock,
    ) as mock_config:
        mock_config.return_value = config
        yield config


@pytest.fixture(autouse=True)
def mock_ocean_context(mock_integration_config: dict[str, str]) -> None | MagicMock:
    """Fixture to initialize the PortOcean context."""
    mock_app = MagicMock()
    mock_app.config.integration.config = mock_integration_config
    try:
        mock_app.cache_provider = AsyncMock()
        mock_app.cache_provider.get.return_value = None
        initialize_port_ocean_context(mock_app)
    except PortOceanContextAlreadyInitializedError:
        # Context already initialized, ignore
        pass
    return None


@pytest.fixture
def mock_datadog_client() -> DatadogClient:
    return DatadogClient(
        api_url="https://api.datadoghq.com",
        api_key="test_api_key",
        app_key="test_app_key",
    )
