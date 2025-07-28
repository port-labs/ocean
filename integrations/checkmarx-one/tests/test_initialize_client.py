import pytest
from unittest.mock import patch, MagicMock
from aiolimiter import AsyncLimiter


from client import CheckmarxAuthenticationError
from initialize_client import init_client, CHECKMARX_MAX_REQUESTS_PER_HOUR, RATE_LIMITER


class TestInitializeClient:

    @patch("initialize_client.ocean")
    def test_init_client_missing_base_url(self, mock_ocean: MagicMock) -> None:
        """Test client initialization failure with missing base URL."""
        # Arrange
        mock_ocean.integration_config = {
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }

        # Act & Assert
        with pytest.raises(
            CheckmarxAuthenticationError,
            match="checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required",
        ):
            init_client()

    @patch("initialize_client.ocean")
    def test_init_client_missing_iam_url(self, mock_ocean: MagicMock) -> None:
        """Test client initialization failure with missing IAM URL."""
        # Arrange
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }

        # Act & Assert
        with pytest.raises(
            CheckmarxAuthenticationError,
            match="checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required",
        ):
            init_client()

    @patch("initialize_client.ocean")
    def test_init_client_missing_tenant(self, mock_ocean: MagicMock) -> None:
        """Test client initialization failure with missing tenant."""
        # Arrange
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_api_key": "test-api-key",
        }

        # Act & Assert
        with pytest.raises(
            CheckmarxAuthenticationError,
            match="checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required",
        ):
            init_client()

    @patch("initialize_client.ocean")
    def test_init_client_missing_all_required_config(
        self, mock_ocean: MagicMock
    ) -> None:
        """Test client initialization failure with all required config missing."""
        # Arrange
        mock_ocean.integration_config = {}

        # Act & Assert
        with pytest.raises(
            CheckmarxAuthenticationError,
            match="checkmarx_base_url, checkmarx_iam_url, and checkmarx_tenant are required",
        ):
            init_client()

    @patch("initialize_client.ocean")
    def test_init_client_missing_auth_credentials(self, mock_ocean: MagicMock) -> None:
        """Test client initialization failure with missing authentication credentials."""
        # Arrange
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            # No auth credentials
        }

        # Act & Assert
        with pytest.raises(CheckmarxAuthenticationError):
            init_client()

    @patch("initialize_client.ocean")
    def test_init_client_incomplete_oauth_credentials(
        self, mock_ocean: MagicMock
    ) -> None:
        """Test client initialization failure with incomplete OAuth credentials."""
        # Arrange - missing client_secret
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_client_id": "test-client-id",
            # Missing checkmarx_client_secret
        }

        # Act & Assert
        with pytest.raises(CheckmarxAuthenticationError):
            init_client()

    @patch("initialize_client.logger")
    @patch("initialize_client.ocean")
    def test_init_client_logs_error_on_auth_failure(
        self, mock_ocean: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test that client initialization logs errors on authentication failure."""
        # Arrange
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            # No auth credentials
        }

        # Act & Assert
        with pytest.raises(CheckmarxAuthenticationError):
            init_client()

        mock_logger.error.assert_called()

    @patch("initialize_client.CheckmarxClient")
    @patch("initialize_client.logger")
    @patch("initialize_client.ocean")
    def test_init_client_logs_error_on_client_creation_failure(
        self,
        mock_ocean: MagicMock,
        mock_logger: MagicMock,
        mock_client_class: MagicMock,
    ) -> None:
        """Test that client initialization logs errors on client creation failure."""
        # Arrange
        mock_ocean.integration_config = {
            "checkmarx_base_url": "https://ast.checkmarx.net",
            "checkmarx_iam_url": "https://iam.checkmarx.net",
            "checkmarx_tenant": "test-tenant",
            "checkmarx_api_key": "test-api-key",
        }
        mock_client_class.side_effect = Exception("Client creation failed")

        # Act & Assert
        with pytest.raises(
            CheckmarxAuthenticationError, match="Client initialization failed"
        ):
            init_client()

        mock_logger.error.assert_called_with(
            "Failed to initialize Checkmarx One client: Client creation failed"
        )

    def test_rate_limiter_constants(self) -> None:
        """Test that rate limiter constants are properly defined."""
        assert CHECKMARX_MAX_REQUESTS_PER_HOUR == 3600
        assert isinstance(RATE_LIMITER, AsyncLimiter)
        assert RATE_LIMITER.max_rate == 3600
        assert RATE_LIMITER.time_period == 3600
