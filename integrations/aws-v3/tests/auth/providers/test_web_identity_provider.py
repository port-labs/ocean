import pytest
from unittest.mock import patch, AsyncMock, ANY
from typing import Any
from aws.auth.providers.web_identity_provider import WebIdentityCredentialProvider
from aws.auth.utils import CredentialsProviderError


class TestWebIdentityCredentialProvider:
    """Tests for WebIdentityCredentialProvider."""

    def test_is_refreshable_property(self) -> None:
        """Test that WebIdentityCredentialProvider is not refreshable."""
        provider = WebIdentityCredentialProvider()
        assert provider.is_refreshable is False

    @pytest.mark.asyncio
    async def test_get_credentials_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error."""
        provider = WebIdentityCredentialProvider()

        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_credentials(oidc_token="test-token")

    @pytest.mark.asyncio
    async def test_get_credentials_missing_oidc_token(self, role_arn: str) -> None:
        """Test that missing oidc_token raises error."""
        provider = WebIdentityCredentialProvider()

        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_credentials(role_arn=role_arn)

    @pytest.mark.asyncio
    async def test_get_credentials_success(
        self, role_arn: str, mock_web_identity_response: Any, mock_aiocredentials: Any
    ) -> None:
        """Test successful credential retrieval."""
        provider = WebIdentityCredentialProvider()

        with patch(
            "aws.auth.providers.web_identity_provider.AioCredentials",
            return_value=mock_aiocredentials,
        ):
            with patch.object(provider, "aws_client_factory_session") as mock_session:
                mock_sts_client = AsyncMock()
                mock_sts_client.assume_role_with_web_identity.return_value = (
                    mock_web_identity_response
                )
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_session.create_client.return_value = mock_context

                credentials = await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                    region="us-east-1",
                )
                assert credentials == mock_aiocredentials

    @pytest.mark.asyncio
    async def test_get_credentials_with_custom_session_name(
        self, role_arn: str, mock_web_identity_response: Any, mock_aiocredentials: Any
    ) -> None:
        """Test credential retrieval with custom session name."""
        provider = WebIdentityCredentialProvider()

        with patch(
            "aws.auth.providers.web_identity_provider.AioCredentials",
            return_value=mock_aiocredentials,
        ):
            with patch.object(provider, "aws_client_factory_session") as mock_session:
                mock_sts_client = AsyncMock()
                mock_sts_client.assume_role_with_web_identity.return_value = (
                    mock_web_identity_response
                )
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_session.create_client.return_value = mock_context

                credentials = await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                    role_session_name="CustomSessionName",
                )
                assert credentials == mock_aiocredentials
                mock_sts_client.assume_role_with_web_identity.assert_called_once_with(
                    RoleArn=role_arn,
                    RoleSessionName="CustomSessionName",
                    WebIdentityToken="test-token",
                )

    @pytest.mark.asyncio
    async def test_get_session_success(
        self, role_arn: str, mock_aiocredentials: Any
    ) -> None:
        """Test successful session retrieval."""
        provider = WebIdentityCredentialProvider()

        with patch(
            "aws.auth.providers.web_identity_provider.AioCredentials",
            return_value=mock_aiocredentials,
        ):
            with patch.object(provider, "aws_client_factory_session") as mock_session:
                mock_sts_client = AsyncMock()
                mock_sts_client.assume_role_with_web_identity.return_value = {
                    "Credentials": {
                        "AccessKeyId": "test_access_key",
                        "SecretAccessKey": "test_secret_key",
                        "SessionToken": "test_session_token",
                        "Expiration": "2023-12-31T23:59:59Z",
                    }
                }
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_session.create_client.return_value = mock_context

                session = await provider.get_session(
                    role_arn=role_arn,
                    oidc_token="test-token",
                )
                assert session is not None

    @pytest.mark.asyncio
    async def test_get_session_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error for session."""
        provider = WebIdentityCredentialProvider()

        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_session(oidc_token="test-token")

    @pytest.mark.asyncio
    async def test_get_session_missing_oidc_token(self, role_arn: str) -> None:
        """Test that missing oidc_token raises error for session."""
        provider = WebIdentityCredentialProvider()

        with pytest.raises(
            CredentialsProviderError, match="Failed to get web identity credentials"
        ):
            await provider.get_session(role_arn=role_arn)

    @pytest.mark.asyncio
    async def test_get_credentials_uses_unsigned_config(
        self, role_arn: str, mock_web_identity_response: Any, mock_aiocredentials: Any
    ) -> None:
        """Test that get_credentials uses unsigned configuration."""
        provider = WebIdentityCredentialProvider()

        with patch(
            "aws.auth.providers.web_identity_provider.AioCredentials",
            return_value=mock_aiocredentials,
        ):
            with patch.object(provider, "aws_client_factory_session") as mock_session:
                mock_sts_client = AsyncMock()
                mock_sts_client.assume_role_with_web_identity.return_value = (
                    mock_web_identity_response
                )
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_session.create_client.return_value = mock_context

                await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                )

                mock_session.create_client.assert_called_once_with(
                    "sts",
                    region_name=None,
                    config=ANY,
                )

    def test_initialization_with_config(self) -> None:
        """Test provider initialization with config."""
        config = {"test_key": "test_value"}
        provider = WebIdentityCredentialProvider(config=config)
        assert provider.config == config

    def test_initialization_without_config(self) -> None:
        """Test provider initialization without config."""
        provider = WebIdentityCredentialProvider()
        assert provider.config == {}

    @pytest.mark.asyncio
    async def test_get_credentials_with_different_regions(
        self, role_arn: str, mock_web_identity_response: Any, mock_aiocredentials: Any
    ) -> None:
        """Test credential retrieval with different regions."""
        provider = WebIdentityCredentialProvider()

        with patch(
            "aws.auth.providers.web_identity_provider.AioCredentials",
            return_value=mock_aiocredentials,
        ):
            with patch.object(provider, "aws_client_factory_session") as mock_session:
                mock_sts_client = AsyncMock()
                mock_sts_client.assume_role_with_web_identity.return_value = (
                    mock_web_identity_response
                )
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_session.create_client.return_value = mock_context

                credentials1 = await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                    region="us-east-1",
                )
                assert credentials1 == mock_aiocredentials

                credentials2 = await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                    region="us-west-2",
                )
                assert credentials2 == mock_aiocredentials

                assert mock_session.create_client.call_count == 2
                calls = mock_session.create_client.call_args_list
                assert calls[0][1]["region_name"] == "us-east-1"
                assert calls[1][1]["region_name"] == "us-west-2"

    @pytest.mark.asyncio
    async def test_get_credentials_with_all_optional_parameters(
        self, role_arn: str, mock_web_identity_response: Any, mock_aiocredentials: Any
    ) -> None:
        """Test credential retrieval with all optional parameters."""
        provider = WebIdentityCredentialProvider()

        with patch(
            "aws.auth.providers.web_identity_provider.AioCredentials",
            return_value=mock_aiocredentials,
        ):
            with patch.object(provider, "aws_client_factory_session") as mock_session:
                mock_sts_client = AsyncMock()
                mock_sts_client.assume_role_with_web_identity.return_value = (
                    mock_web_identity_response
                )
                mock_context = AsyncMock()
                mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                mock_context.__aexit__ = AsyncMock(return_value=None)
                mock_session.create_client.return_value = mock_context

                credentials = await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                    region="us-east-1",
                    role_session_name="CustomSession",
                    duration_seconds=3600,
                )
                assert credentials == mock_aiocredentials

                mock_sts_client.assume_role_with_web_identity.assert_called_once_with(
                    RoleArn=role_arn,
                    RoleSessionName="CustomSession",
                    WebIdentityToken="test-token",
                )

    @pytest.mark.asyncio
    async def test_get_credentials_sts_client_creation_failure(
        self, role_arn: str
    ) -> None:
        """Test credential retrieval when STS client creation fails."""
        provider = WebIdentityCredentialProvider()

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.side_effect = Exception(
                "STS client creation failed"
            )

            with pytest.raises(
                CredentialsProviderError, match="Failed to get web identity credentials"
            ):
                await provider.get_credentials(
                    role_arn=role_arn,
                    oidc_token="test-token",
                )
