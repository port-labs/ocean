from pydantic import BaseModel
import pytest
from unittest.mock import MagicMock, mock_open, patch
from port_ocean.ocean import Ocean
from port_ocean.config.settings import IntegrationConfiguration, IntegrationSettings


@pytest.fixture
def mock_ocean() -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean_mock = Ocean()
        ocean_mock.config = MagicMock(spec=IntegrationConfiguration)
        return ocean_mock


def test_load_external_integration_config_no_config_file(mock_ocean: Ocean) -> None:
    # Setup
    mock_ocean.config.config_file_path = None
    mock_ocean.config.integration = MagicMock(spec=IntegrationSettings)
    mock_ocean.config.integration.config = MagicMock(spec=BaseModel)
    mock_ocean.config.integration.config.dict.return_value = {"key1": "value1"}

    # Execute
    result = mock_ocean.load_external_integration_config()

    # Assert
    assert result == {"key1": "value1"}
    mock_ocean.config.integration.config.dict.assert_called_once()


def test_load_external_integration_config_with_file(mock_ocean: Ocean) -> None:
    # Setup
    mock_ocean.config.config_file_path = "/path/to/config.yaml"
    mock_ocean.config.integration = MagicMock(spec=IntegrationSettings)
    mock_ocean.config.integration.config = MagicMock(spec=BaseModel)
    mock_ocean.config.integration.config.dict.return_value = {
        "key1": "value1",
        "key2": "value2",
    }
    mock_file_content = """
    key2: new_value2
    key3: value3
    """

    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        # Execute
        result = mock_ocean.load_external_integration_config()

        # Assert
        assert result == {
            "key1": "value1",
            "key2": "new_value2",  # Value from file overrides original
            "key3": "value3",  # New key from file
        }
        mock_ocean.config.integration.config.dict.assert_called_once()


def test_load_external_integration_config_with_empty_file(mock_ocean: Ocean) -> None:
    # Setup
    mock_ocean.config.config_file_path = "/path/to/config.yaml"

    mock_ocean.config.integration = MagicMock(spec=IntegrationSettings)
    mock_ocean.config.integration.config = MagicMock(spec=BaseModel)
    mock_ocean.config.integration.config.dict.return_value = {"key1": "value1"}
    mock_file_content = ""

    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        # Execute
        result = mock_ocean.load_external_integration_config()

        # Assert
        assert result == {"key1": "value1"}
        mock_ocean.config.integration.config.dict.assert_called_once()
