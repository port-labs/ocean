import pytest
from unittest.mock import patch, AsyncMock
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioRefreshableCredentials

from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.utils import CredentialsProviderError
from tests.conftest import (
    AWS_TEST_ACCESS_KEY,
    AWS_TEST_SECRET_KEY,
    AWS_TEST_SESSION_TOKEN,
    AWS_TEST_EXPIRATION,
)


class TestAssumeRoleProvider:
    def test_is_refreshable_property(self) -> None:
        """Test that AssumeRoleProvider is refreshable."""
        # Arrange & Act
        provider = AssumeRoleProvider()

        # Assert
        assert provider.is_refreshable is True

    @pytest.mark.asyncio
    async def test_get_credentials_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error in get_credentials."""
        # Arrange
        provider = AssumeRoleProvider()

        # Act & Assert
        with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
            await provider.get_credentials(region="us-west-2")

    @pytest.mark.asyncio
    async def test_get_session_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error in get_session."""
        # Arrange
        provider = AssumeRoleProvider()

        # Act & Assert
        with pytest.raises(CredentialsProviderError, match="role_arn is required"):
            await provider.get_session(region="us-west-2")

    @pytest.mark.asyncio
    async def test_get_credentials_success(self, role_arn: str) -> None:
        """Test successful credential retrieval."""
        # Arrange
        provider = AssumeRoleProvider()

        mock_refresher = AsyncMock()
        mock_refresher.return_value = {
            "access_key": AWS_TEST_ACCESS_KEY,
            "secret_key": AWS_TEST_SECRET_KEY,
            "token": AWS_TEST_SESSION_TOKEN,
            "expiry_time": AWS_TEST_EXPIRATION,
        }

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_refresher,
        ):
            # Act
            credentials = await provider.get_credentials(
                role_arn=role_arn,
                region="us-west-2",
            )

            # Assert
            assert isinstance(credentials, AioRefreshableCredentials)

    @pytest.mark.asyncio
    async def test_get_credentials_with_external_id(self, role_arn: str) -> None:
        """Test credential retrieval with external ID."""
        # Arrange
        provider = AssumeRoleProvider()

        mock_refresher = AsyncMock()
        mock_refresher.return_value = {
            "access_key": AWS_TEST_ACCESS_KEY,
            "secret_key": AWS_TEST_SECRET_KEY,
            "token": AWS_TEST_SESSION_TOKEN,
            "expiry_time": AWS_TEST_EXPIRATION,
        }

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_refresher,
        ):
            # Act
            credentials = await provider.get_credentials(
                role_arn=role_arn,
                region="us-west-2",
                external_id="test-external-id",
            )

            # Assert
            assert isinstance(credentials, AioRefreshableCredentials)

    @pytest.mark.asyncio
    async def test_get_credentials_error_propagation(self, role_arn: str) -> None:
        """Test that errors are properly propagated."""
        # Arrange
        provider = AssumeRoleProvider()

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            side_effect=Exception("STS client error"),
        ):
            # Act & Assert
            with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
                await provider.get_credentials(
                    role_arn=role_arn,
                    region="us-west-2",
                )

    @pytest.mark.asyncio
    async def test_get_session_success(self, role_arn: str) -> None:
        """Test successful session creation."""
        # Arrange
        provider = AssumeRoleProvider()

        mock_refresher = AsyncMock()
        mock_refresher.return_value = {
            "access_key": AWS_TEST_ACCESS_KEY,
            "secret_key": AWS_TEST_SECRET_KEY,
            "token": AWS_TEST_SESSION_TOKEN,
            "expiry_time": AWS_TEST_EXPIRATION,
        }

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_refresher,
        ):
            # Act
            session = await provider.get_session(
                role_arn=role_arn,
                region="us-west-2",
            )

            # Assert
            assert isinstance(session, AioSession)
            assert hasattr(session, "_credentials")

    def test_initialization_with_config(self) -> None:
        """Test provider initialization with config."""
        # Arrange
        config = {"region": "us-east-1"}

        # Act
        provider = AssumeRoleProvider(config)

        # Assert
        assert provider.config == config

    def test_initialization_without_config(self) -> None:
        """Test provider initialization without config."""
        # Arrange & Act
        provider = AssumeRoleProvider()

        # Assert
        assert provider.config == {}

    @pytest.mark.asyncio
    async def test_get_credentials_sts_client_creation_failure(
        self, role_arn: str
    ) -> None:
        """Test get_credentials handles STS client creation failure."""
        provider = AssumeRoleProvider()

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            side_effect=Exception("STS client creation failed"),
        ):
            with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
                await provider.get_credentials(
                    role_arn=role_arn,
                    region="us-west-2",
                )
