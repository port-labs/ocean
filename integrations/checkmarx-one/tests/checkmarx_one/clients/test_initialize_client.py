import pytest
from unittest.mock import patch, MagicMock

from checkmarx_one.clients.initialize_client import (
    get_checkmarx_client,
    CheckmarxOneClientSingleton,
)
from checkmarx_one.clients.client import CheckmarxOneClient
from checkmarx_one.exceptions import CheckmarxAuthenticationError


class TestInitializeClient:
    """Test cases for initialize_client module."""

    def setup_method(self) -> None:
        """Reset the singleton before each test."""
        CheckmarxOneClientSingleton._instance = None

    @pytest.fixture
    def mock_ocean_config(self) -> dict[str, str]:
        """Create a mock Ocean configuration."""
        return {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }

    @pytest.fixture
    def mock_ocean_oauth_config(self) -> dict[str, str]:
        """Create a mock Ocean OAuth configuration."""
        return {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
        }

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    def test_init_client_with_api_key(
        self,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test client initialization with API key authentication."""
        mock_ocean.integration_config = mock_ocean_config
        mock_authenticator = MagicMock()
        mock_auth_factory.create_authenticator.return_value = mock_authenticator
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client_class.return_value = mock_client

        result = get_checkmarx_client()

        assert result == mock_client
        mock_client_class.assert_called_once_with(
            base_url="https://ast.checkmarx.net",
            authenticator=mock_authenticator,
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
            get_checkmarx_client()

        assert "Client initialization failed: 'checkmarx_base_url'" in str(
            exc_info.value
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
            get_checkmarx_client()

        assert "Client initialization failed: 'checkmarx_iam_url'" in str(
            exc_info.value
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
            get_checkmarx_client()

        assert "Client initialization failed: 'checkmarx_tenant'" in str(exc_info.value)

    @patch("checkmarx_one.clients.initialize_client.ocean")
    def test_init_client_missing_all_required_config(
        self, mock_ocean: MagicMock
    ) -> None:
        """Test client initialization with missing all required configuration."""
        mock_ocean.integration_config = {}

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            get_checkmarx_client()

        assert "Client initialization failed: 'checkmarx_base_url'" in str(
            exc_info.value
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    def test_init_client_with_empty_strings(
        self,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
    ) -> None:
        """Test client initialization with empty string values."""
        mock_ocean.integration_config = {
            "checkmarx_base_url": "",
            "checkmarx_iam_url": "",
            "checkmarx_tenant": "",
            "checkmarx_api_key": "test-api-key",
        }
        mock_authenticator = MagicMock()
        mock_auth_factory.create_authenticator.return_value = mock_authenticator
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client_class.return_value = mock_client

        # Should not raise an error, just use empty strings
        result = get_checkmarx_client()
        assert result == mock_client

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    def test_init_client_with_none_values(
        self,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
    ) -> None:
        """Test client initialization with None values."""
        mock_ocean.integration_config = {
            "checkmarx_base_url": None,
            "checkmarx_iam_url": None,
            "checkmarx_tenant": None,
            "checkmarx_api_key": "test-api-key",
        }
        mock_authenticator = MagicMock()
        mock_auth_factory.create_authenticator.return_value = mock_authenticator
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client_class.return_value = mock_client

        # Should not raise an error, just use None values
        result = get_checkmarx_client()
        assert result == mock_client

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    def test_init_client_authentication_error(
        self,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test client initialization when authentication fails."""
        mock_ocean.integration_config = mock_ocean_config
        mock_auth_factory.create_authenticator.side_effect = (
            CheckmarxAuthenticationError("Auth failed")
        )

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            get_checkmarx_client()

        assert "Auth failed" in str(exc_info.value)

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    def test_init_client_general_exception(
        self,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test client initialization when general exception occurs."""
        mock_ocean.integration_config = mock_ocean_config
        mock_auth_factory.create_authenticator.side_effect = Exception("General error")

        with pytest.raises(CheckmarxAuthenticationError) as exc_info:
            get_checkmarx_client()

        assert "Client initialization failed: General error" in str(exc_info.value)

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_info_message(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test that info message is logged during client initialization."""
        mock_ocean.integration_config = mock_ocean_config
        mock_authenticator = MagicMock()
        mock_auth_factory.create_authenticator.return_value = mock_authenticator
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client_class.return_value = mock_client

        get_checkmarx_client()

        mock_logger.info.assert_any_call(
            "Initializing Checkmarx One client for https://ast.checkmarx.net"
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxOneClient")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_api_key_auth(
        self,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test that API key authentication is logged."""
        mock_ocean.integration_config = mock_ocean_config
        mock_authenticator = MagicMock()
        mock_auth_factory.create_authenticator.return_value = mock_authenticator
        mock_client = MagicMock(spec=CheckmarxOneClient)
        mock_client_class.return_value = mock_client

        get_checkmarx_client()

        mock_auth_factory.create_authenticator.assert_called_once_with(
            iam_url="https://iam.checkmarx.net",
            tenant="test-tenant",
            api_key="test-api-key",
        )

    def test_init_client_logs_oauth_auth(self) -> None:
        """This integration no longer supports OAuth; this test is removed."""
        pass

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_error_on_auth_failure(
        self,
        mock_logger: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test that error is logged on authentication failure."""
        mock_ocean.integration_config = mock_ocean_config
        mock_auth_factory.create_authenticator.side_effect = (
            CheckmarxAuthenticationError("Auth failed")
        )

        with pytest.raises(CheckmarxAuthenticationError):
            get_checkmarx_client()

        mock_logger.error.assert_called_with(
            "Authentication configuration error: Auth failed"
        )

    @patch("checkmarx_one.clients.initialize_client.ocean")
    @patch("checkmarx_one.clients.initialize_client.CheckmarxAuthenticatorFactory")
    @patch("checkmarx_one.clients.initialize_client.logger")
    def test_init_client_logs_error_on_general_failure(
        self,
        mock_logger: MagicMock,
        mock_auth_factory: MagicMock,
        mock_ocean: MagicMock,
        mock_ocean_config: dict[str, str],
    ) -> None:
        """Test that error is logged on general failure."""
        mock_ocean.integration_config = mock_ocean_config
        mock_auth_factory.create_authenticator.side_effect = Exception("General error")

        with pytest.raises(CheckmarxAuthenticationError):
            get_checkmarx_client()

        mock_logger.error.assert_called_with(
            "Failed to initialize Checkmarx One client: General error"
        )
