import pytest
from unittest.mock import MagicMock, mock_open, patch
from port_ocean.ocean import Ocean
from port_ocean.config.settings import IntegrationConfiguration


@pytest.fixture
def mock_ocean() -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean_mock = Ocean()
        ocean_mock.config = MagicMock(spec=IntegrationConfiguration)
        return ocean_mock


def test_load_external_oauth_access_token_no_file(mock_ocean: Ocean) -> None:
    # Setup
    mock_ocean.config.oauth_access_token_file_path = None

    # Execute
    result = mock_ocean.load_external_oauth_access_token()

    # Assert
    assert result is None


def test_load_external_oauth_access_token_with_file(mock_ocean: Ocean) -> None:
    # Setup
    mock_ocean.config.oauth_access_token_file_path = "/path/to/token.txt"
    mock_file_content = "test_access_token"

    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        # Execute
        result = mock_ocean.load_external_oauth_access_token()

        # Assert
        assert result == "test_access_token"


def test_load_external_oauth_access_token_with_empty_file(mock_ocean: Ocean) -> None:
    # Setup
    mock_ocean.config.oauth_access_token_file_path = "/path/to/token.txt"
    mock_file_content = ""

    with patch("builtins.open", mock_open(read_data=mock_file_content)):
        # Execute
        result = mock_ocean.load_external_oauth_access_token()

        # Assert
        assert result == ""
