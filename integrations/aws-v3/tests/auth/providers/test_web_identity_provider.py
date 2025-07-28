import pytest
from unittest.mock import patch, AsyncMock
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials

from aws.auth.providers.web_identity_provider import WebIdentityCredentialProvider
from aws.auth.utils import CredentialsProviderError
from tests.conftest import (
    AWS_TEST_ACCESS_KEY,
    AWS_TEST_SECRET_KEY,
    AWS_TEST_SESSION_TOKEN,
    AWS_STS_CREDENTIALS_RESPONSE,
)


class TestWebIdentityCredentialProvider:
    """Tests for WebIdentityCredentialProvider."""

    def test_is_refreshable_property(self) -> None:
        """Test that WebIdentityCredentialProvider is not refreshable."""
        # Arrange & Act
        provider = WebIdentityCredentialProvider()

        # Assert
        assert provider.is_refreshable is False

    @pytest.mark.asyncio
    async def test_get_credentials_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        # Act & Assert
        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_credentials(oidc_token="test-token")

    @pytest.mark.asyncio
    async def test_get_credentials_missing_oidc_token(self, role_arn: str) -> None:
        """Test that missing oidc_token raises error."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        # Act & Assert
        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_credentials(role_arn=role_arn)

    @pytest.mark.asyncio
    async def test_get_credentials_success(self, role_arn: str) -> None:
        """Test successful credential retrieval."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        mock_sts_client = AsyncMock()
        mock_sts_client.assume_role_with_web_identity.return_value = (
            AWS_STS_CREDENTIALS_RESPONSE
        )

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.return_value.__aenter__.return_value = (
                mock_sts_client
            )
            mock_session.create_client.return_value.__aexit__.return_value = None

            # Act
            credentials = await provider.get_credentials(
                role_arn=role_arn,
                oidc_token="test-token",
                region="us-east-1",
            )

            # Assert
            assert isinstance(credentials, AioCredentials)
            assert credentials.access_key == AWS_TEST_ACCESS_KEY
            assert credentials.secret_key == AWS_TEST_SECRET_KEY
            assert credentials.token == AWS_TEST_SESSION_TOKEN

    @pytest.mark.asyncio
    async def test_get_credentials_with_custom_session_name(
        self, role_arn: str
    ) -> None:
        """Test credential retrieval with custom session name."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        mock_sts_client = AsyncMock()
        mock_sts_client.assume_role_with_web_identity.return_value = (
            AWS_STS_CREDENTIALS_RESPONSE
        )

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.return_value.__aenter__.return_value = (
                mock_sts_client
            )
            mock_session.create_client.return_value.__aexit__.return_value = None

            # Act
            credentials = await provider.get_credentials(
                role_arn=role_arn,
                oidc_token="test-token",
                role_session_name="CustomSessionName",
            )

            # Assert
            assert isinstance(credentials, AioCredentials)

    @pytest.mark.asyncio
    async def test_get_session_success(self, role_arn: str) -> None:
        """Test successful session creation."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        mock_sts_client = AsyncMock()
        mock_sts_client.assume_role_with_web_identity.return_value = (
            AWS_STS_CREDENTIALS_RESPONSE
        )

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.return_value.__aenter__.return_value = (
                mock_sts_client
            )
            mock_session.create_client.return_value.__aexit__.return_value = None

            # Act
            session = await provider.get_session(
                role_arn=role_arn,
                oidc_token="test-token",
            )

            # Assert
            assert isinstance(session, AioSession)
            assert hasattr(session, "_credentials")
            assert session._credentials.access_key == AWS_TEST_ACCESS_KEY

    @pytest.mark.asyncio
    async def test_get_session_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error for session."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        # Act & Assert
        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_session(oidc_token="test-token")

    @pytest.mark.asyncio
    async def test_get_session_missing_oidc_token(self, role_arn: str) -> None:
        """Test that missing oidc_token raises error for session."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        # Act & Assert
        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_session(role_arn=role_arn)

    @pytest.mark.asyncio
    async def test_get_credentials_sts_client_creation_failure(
        self, role_arn: str
    ) -> None:
        """Test credential retrieval when STS client creation fails."""
        # Arrange
        provider = WebIdentityCredentialProvider()

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.side_effect = Exception(
                "STS client creation failed"
            )

            # Act & Assert
            with pytest.raises(
                CredentialsProviderError, match="Failed to get web identity credentials"
            ):
                await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                )

    def test_initialization_with_config(self) -> None:
        """Test provider initialization with config."""
        # Arrange
        config = {"test_key": "test_value"}

        # Act
        provider = WebIdentityCredentialProvider(config=config)

        # Assert
        assert provider.config == config

    def test_initialization_without_config(self) -> None:
        """Test provider initialization without config."""
        # Arrange & Act
        provider = WebIdentityCredentialProvider()

        # Assert
        assert provider.config == {}
