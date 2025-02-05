import pytest
from unittest.mock import AsyncMock

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.exceptions.api import EmptyPortAppConfigError


@pytest.fixture
def mock_context() -> AsyncMock:
    context = AsyncMock()
    context.port_client.get_current_integration = AsyncMock()
    return context


@pytest.fixture
def api_config(mock_context: AsyncMock) -> APIPortAppConfig:
    return APIPortAppConfig(mock_context)


async def test_get_port_app_config_valid_config_returns_config(
    api_config: APIPortAppConfig, mock_context: AsyncMock
) -> None:
    # Arrange
    expected_config = {"key": "value"}
    mock_context.port_client.get_current_integration.return_value = {
        "config": expected_config
    }

    # Act
    result = await api_config._get_port_app_config()

    # Assert
    assert result == expected_config
    mock_context.port_client.get_current_integration.assert_called_once()


async def test_get_port_app_config_empty_config_raises_value_error(
    api_config: APIPortAppConfig, mock_context: AsyncMock
) -> None:
    # Arrange
    mock_context.port_client.get_current_integration.return_value = {"config": {}}

    # Act & Assert
    with pytest.raises(EmptyPortAppConfigError, match="Port app config is empty"):
        await api_config._get_port_app_config()


async def test_get_port_app_config_missing_config_key_raises_key_error(
    api_config: APIPortAppConfig, mock_context: AsyncMock
) -> None:
    # Arrange
    mock_context.port_client.get_current_integration.return_value = {}

    # Act & Assert
    with pytest.raises(KeyError):
        await api_config._get_port_app_config()


async def test_get_port_app_config_empty_integration_raises_key_error(
    api_config: APIPortAppConfig, mock_context: AsyncMock
) -> None:
    # Arrange
    mock_context.port_client.get_current_integration.return_value = {}

    # Act & Assert
    with pytest.raises(KeyError):
        await api_config._get_port_app_config()
