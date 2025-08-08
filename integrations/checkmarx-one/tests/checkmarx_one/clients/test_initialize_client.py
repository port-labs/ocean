import pytest
from unittest.mock import patch, MagicMock

from checkmarx_one.clients.initialize_client import init_client
from checkmarx_one.clients.client import CheckmarxClient
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class TestInitializeClient:
    """Test cases for initialize_client module."""

    @pytest.fixture
    def mock_ocean_config(self) -> dict:
        """Create a mock Ocean configuration."""
        return {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }

    @pytest.fixture
    def mock_ocean_oauth_config(self) -> dict:
        """Create a mock Ocean OAuth configuration."""
        return {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_client_id": "test-client-id",
            "checkmarx_client_secret": "test-client-secret",
        }

    @pytest.fixture
    def mock_checkmarx_client(self) -> MagicMock:
        """Create a mock CheckmarxClient."""
        mock_client = MagicMock(spec=CheckmarxClient)
        mock_client.base_url = "https://ast.checkmarx.net"
        mock_client.iam_url = "https://iam.checkmarx.net"
        mock_client.tenant = "test-tenant"
        return mock_client

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    def test_init_client_with_api_key(
        self,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test client initialization with API key authentication."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.return_value = mock_checkmarx_client

        result = init_client()

        assert result == mock_checkmarx_client
        mock_client_class.assert_called_once_with(
            base_url="https://ast.checkmarx.net",
            iam_url="https://iam.checkmarx.net",
            tenant="test-tenant",
            api_key="test-api-key",
            client_id=None,
            client_secret=None,
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    def test_init_client_with_oauth(
        self,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_oauth_config: dict,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test client initialization with OAuth authentication."""
        mock_ocean.integration_config = mock_ocean_oauth_config
        mock_client_class.return_value = mock_checkmarx_client

        result = init_client()

        assert result == mock_checkmarx_client
        mock_client_class.assert_called_once_with(
            base_url="https://ast.checkmarx.net",
            iam_url="https://iam.checkmarx.net",
            tenant="test-tenant",
            api_key=None,
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    def test_init_client_missing_base_url(self, mock_ocean: MagicMock) -> None:
        """Test client initialization with missing base URL."""
        mock_ocean.integration_config = {
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert (
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
            in str(exc_info.value)
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    def test_init_client_missing_iam_url(self, mock_ocean: MagicMock) -> None:
        """Test client initialization with missing IAM URL."""
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert (
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
            in str(exc_info.value)
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    def test_init_client_missing_tenant(self, mock_ocean: MagicMock) -> None:
        """Test client initialization with missing tenant."""
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_api_key": "test-api-key",
        }

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert (
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
            in str(exc_info.value)
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    def test_init_client_missing_all_required_config(
        self, mock_ocean: MagicMock
    ) -> None:
        """Test client initialization with missing all required configuration."""
        mock_ocean.integration_config = {}

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert (
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
            in str(exc_info.value)
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    def test_init_client_with_empty_strings(
        self,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test client initialization with empty string values."""
        mock_ocean.integration_config = {
            "checkmarx_base_url": "",
            "checkmarx_iam_url": "",
            "checkmarx_tenant": "",
            "checkmarx_api_key": "test-api-key",
        }
        mock_client_class.return_value = mock_checkmarx_client

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert (
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
            in str(exc_info.value)
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    def test_init_client_with_none_values(
        self,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test client initialization with None values."""
        mock_ocean.integration_config = {
            "checkmarx_base_url": None,
            "checkmarx_iam_url": None,
            "checkmarx_tenant": None,
            "checkmarx_api_key": "test-api-key",
        }
        mock_client_class.return_value = mock_checkmarx_client

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert (
            "checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required"
            in str(exc_info.value)
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    def test_init_client_authentication_error(
        self,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
    ) -> None:
        """Test client initialization when authentication fails."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.side_effect = CheckmarxAuthenticationError("Auth failed")

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert "Auth failed" in str(exc_info.value)

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    def test_init_client_general_exception(
        self,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
    ) -> None:
        """Test client initialization when general exception occurs."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.side_effect = Exception("General error")

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            init_client()

        assert "Client initialization failed: General error" in str(exc_info.value)

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_info_message(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test that info message is logged during client initialization."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.return_value = mock_checkmarx_client

        init_client()

        mock_logger.info.assert_any_call(
            "Initializing Checkmarx One client for https://ast.checkmarx.net"
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_api_key_auth(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test that API key authentication is logged."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.return_value = mock_checkmarx_client

        init_client()

        mock_logger.info.assert_any_call("Using API key authentication")

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_oauth_auth(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_oauth_config: dict,
        mock_checkmarx_client: MagicMock,
    ) -> None:
        """Test that OAuth authentication is logged."""
        mock_ocean.integration_config = mock_ocean_oauth_config
        mock_client_class.return_value = mock_checkmarx_client

        init_client()

        mock_logger.info.assert_any_call(
            "Using OAuth authentication with client: test-client-id"
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_error_on_auth_failure(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
    ) -> None:
        """Test that error is logged on authentication failure."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.side_effect = CheckmarxAuthenticationError("Auth failed")

        with pytest.raises(CheckmarxAuthenticationError):
            init_client()

        mock_logger.error.assert_called_with(
            "Authentication configuration error: Auth failed"
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_error_on_general_failure(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict,
    ) -> None:
        """Test that error is logged on general failure."""
        mock_ocean.integration_config = mock_ocean_config
        mock_client_class.side_effect = Exception("General error")

        with pytest.raises(CheckmarxAuthenticationError):
            init_client()

        mock_logger.error.assert_called_with(
            "Failed to initialize Checkmarx One client: General error"
        )
