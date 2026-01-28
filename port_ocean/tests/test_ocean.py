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


@pytest.fixture
def mock_ocean_with_integration_config() -> Ocean:
    with patch("port_ocean.ocean.Ocean.__init__", return_value=None):
        ocean_mock = Ocean()
        ocean_mock.config = MagicMock()
        ocean_mock.config.integration = MagicMock()
        ocean_mock.config.integration.config = {}
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


# route_prefix property tests
class TestRoutePrefix:
    @pytest.mark.parametrize(
        "path_prefix,expected",
        [
            ("my-prefix", "/my-prefix"),
            ("/my-prefix", "/my-prefix"),
            ("my-prefix/", "/my-prefix"),
            ("/my-prefix/", "/my-prefix"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_route_prefix_normalizes_slashes(
        self, mock_ocean: Ocean, path_prefix: str | None, expected: str
    ) -> None:
        mock_ocean.config.path_prefix = path_prefix

        assert mock_ocean.route_prefix == expected


# initialize_app route registration tests
class TestInitializeAppRoutes:
    @pytest.mark.parametrize(
        "path_prefix,expected_integration_path,expected_metrics_path",
        [
            (None, "/integration", "/metrics"),
            ("", "/integration", "/metrics"),
            ("my-prefix", "/my-prefix/integration", "/my-prefix/metrics"),
            ("/my-prefix/", "/my-prefix/integration", "/my-prefix/metrics"),
        ],
    )
    def test_initialize_app_registers_routes_with_correct_prefix(
        self,
        mock_ocean: Ocean,
        path_prefix: str | None,
        expected_integration_path: str,
        expected_metrics_path: str,
    ) -> None:
        mock_ocean.config.path_prefix = path_prefix
        mock_ocean.fast_api_app = MagicMock()
        mock_ocean.integration_router = MagicMock()
        mock_ocean.metrics = MagicMock()
        mock_ocean.metrics.create_mertic_router.return_value = MagicMock()

        mock_ocean.initialize_app()

        calls = mock_ocean.fast_api_app.include_router.call_args_list
        assert calls[0].kwargs["prefix"] == expected_integration_path
        assert calls[1].kwargs["prefix"] == expected_metrics_path


# base_url property tests
class TestBaseUrl:
    @pytest.mark.parametrize(
        "base_url,path_prefix,expected",
        [
            ("https://example.com", "my-prefix", "https://example.com/my-prefix"),
            ("https://example.com/", "my-prefix", "https://example.com/my-prefix"),
            ("https://example.com", "/my-prefix/", "https://example.com/my-prefix"),
            ("https://example.com/", "/my-prefix/", "https://example.com/my-prefix"),
            ("https://example.com", None, "https://example.com"),
            ("https://example.com/", None, "https://example.com/"),
        ],
    )
    def test_base_url_constructs_correct_url(
        self,
        mock_ocean_with_integration_config: Ocean,
        base_url: str,
        path_prefix: str | None,
        expected: str,
    ) -> None:
        mock_ocean_with_integration_config.config.base_url = base_url
        mock_ocean_with_integration_config.config.path_prefix = path_prefix

        assert mock_ocean_with_integration_config.base_url == expected
