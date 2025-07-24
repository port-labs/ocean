import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Any
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.utils import CredentialsProviderError


class TestAssumeRoleProvider:
    def test_is_refreshable_property(self) -> None:
        """Test that AssumeRoleProvider is refreshable."""
        provider = AssumeRoleProvider()
        assert provider.is_refreshable is True

    @pytest.mark.asyncio
    async def test_get_credentials_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error."""
        provider = AssumeRoleProvider()

        with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
            await provider.get_credentials(region="us-west-2")

    @pytest.mark.asyncio
    async def test_get_session_missing_role_arn(self) -> None:
        """Test that missing role_arn raises error in get_session."""
        provider = AssumeRoleProvider()

        with pytest.raises(CredentialsProviderError, match="role_arn is required"):
            await provider.get_session(region="us-west-2")

    @pytest.mark.asyncio
    async def test_get_credentials_success(
        self,
        role_arn: str,
        mock_assume_role_refresher: Any,
        mock_aiorefreshable_credentials: Any,
    ) -> None:
        """Test successful credential retrieval."""
        provider = AssumeRoleProvider()

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_assume_role_refresher,
        ):
            with patch(
                "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata",
                return_value=mock_aiorefreshable_credentials,
            ):
                with patch.object(
                    provider, "aws_client_factory_session"
                ) as mock_session:
                    mock_sts_client = AsyncMock()
                    mock_context = AsyncMock()
                    mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                    mock_context.__aexit__ = AsyncMock(return_value=None)
                    mock_session.create_client.return_value = mock_context

                    credentials = await provider.get_credentials(
                        role_arn=role_arn,
                        region="us-west-2",
                    )
                    assert credentials == mock_aiorefreshable_credentials

    @pytest.mark.asyncio
    async def test_get_credentials_with_external_id(
        self,
        role_arn: str,
        mock_assume_role_refresher: Any,
        mock_aiorefreshable_credentials: Any,
    ) -> None:
        """Test credential retrieval with external ID."""
        provider = AssumeRoleProvider()

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_assume_role_refresher,
        ):
            with patch(
                "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata",
                return_value=mock_aiorefreshable_credentials,
            ):
                with patch.object(
                    provider, "aws_client_factory_session"
                ) as mock_session:
                    mock_sts_client = AsyncMock()
                    mock_context = AsyncMock()
                    mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                    mock_context.__aexit__ = AsyncMock(return_value=None)
                    mock_session.create_client.return_value = mock_context

                    credentials = await provider.get_credentials(
                        role_arn=role_arn,
                        region="us-west-2",
                        external_id="test-external-id",
                    )
                    assert credentials == mock_aiorefreshable_credentials

    @pytest.mark.asyncio
    async def test_get_credentials_error_propagation(self, role_arn: str) -> None:
        """Test that errors are properly propagated."""
        provider = AssumeRoleProvider()

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.side_effect = Exception("STS client error")

            with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
                await provider.get_credentials(
                    role_arn=role_arn,
                    region="us-west-2",
                )

    @pytest.mark.asyncio
    async def test_get_session_success(
        self, role_arn: str, mock_aiorefreshable_credentials: Any
    ) -> None:
        """Test successful session creation."""
        provider = AssumeRoleProvider()

        with patch.object(
            provider, "get_credentials", return_value=mock_aiorefreshable_credentials
        ):
            with patch(
                "aws.auth.providers.assume_role_provider.AioSession"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                session = await provider.get_session(
                    role_arn=role_arn,
                    region="us-west-2",
                )
                assert session == mock_session
                assert hasattr(session, "_credentials")
                assert session._credentials == mock_aiorefreshable_credentials

    def test_initialization_with_config(self) -> None:
        """Test provider initialization with config."""
        config = {"region": "us-east-1"}
        provider = AssumeRoleProvider(config)
        assert provider.config == config

    def test_initialization_without_config(self) -> None:
        """Test provider initialization without config."""
        provider = AssumeRoleProvider()
        assert provider.config == {}

    @pytest.mark.asyncio
    async def test_get_credentials_with_different_regions(
        self,
        role_arn: str,
        mock_assume_role_refresher: Any,
        mock_aiorefreshable_credentials: Any,
    ) -> None:
        """Test get_credentials with different AWS regions."""
        provider = AssumeRoleProvider()

        test_regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]

        for region in test_regions:
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                return_value=mock_assume_role_refresher,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata",
                    return_value=mock_aiorefreshable_credentials,
                ):
                    with patch.object(
                        provider, "aws_client_factory_session"
                    ) as mock_session:
                        mock_sts_client = AsyncMock()
                        mock_context = AsyncMock()
                        mock_context.__aenter__ = AsyncMock(
                            return_value=mock_sts_client
                        )
                        mock_context.__aexit__ = AsyncMock(return_value=None)
                        mock_session.create_client.return_value = mock_context

                        credentials = await provider.get_credentials(
                            role_arn=role_arn,
                            region=region,
                        )
                        assert credentials == mock_aiorefreshable_credentials
                        # Verify the session was created with the correct region
                        mock_session.create_client.assert_called_with(
                            "sts", region_name=region
                        )

    @pytest.mark.asyncio
    async def test_get_credentials_refresh_behavior(
        self,
        role_arn: str,
        mock_assume_role_refresher: Any,
        mock_aiorefreshable_credentials: Any,
    ) -> None:
        """Test that credentials are properly configured for refresh behavior."""
        provider = AssumeRoleProvider()

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_assume_role_refresher,
        ):
            with patch(
                "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
            ) as mock_create_creds:
                mock_create_creds.return_value = mock_aiorefreshable_credentials
                with patch.object(
                    provider, "aws_client_factory_session"
                ) as mock_session:
                    mock_sts_client = AsyncMock()
                    mock_context = AsyncMock()
                    mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                    mock_context.__aexit__ = AsyncMock(return_value=None)
                    mock_session.create_client.return_value = mock_context

                    credentials = await provider.get_credentials(
                        role_arn=role_arn,
                        region="us-west-2",
                    )
                    assert credentials == mock_aiorefreshable_credentials
                    # Verify AioRefreshableCredentials was created with correct parameters
                    mock_create_creds.assert_called_once()
                    call_args = mock_create_creds.call_args
                    assert call_args[1]["method"] == "sts-assume-role"
                    assert call_args[1]["refresh_using"] is not None

    @pytest.mark.asyncio
    async def test_get_credentials_with_all_optional_parameters(
        self,
        role_arn: str,
        mock_assume_role_refresher: Any,
        mock_aiorefreshable_credentials: Any,
    ) -> None:
        """Test get_credentials with all optional parameters provided."""
        provider = AssumeRoleProvider()

        with patch(
            "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
            return_value=mock_assume_role_refresher,
        ):
            with patch(
                "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata",
                return_value=mock_aiorefreshable_credentials,
            ):
                with patch.object(
                    provider, "aws_client_factory_session"
                ) as mock_session:
                    mock_sts_client = AsyncMock()
                    mock_context = AsyncMock()
                    mock_context.__aenter__ = AsyncMock(return_value=mock_sts_client)
                    mock_context.__aexit__ = AsyncMock(return_value=None)
                    mock_session.create_client.return_value = mock_context

                    credentials = await provider.get_credentials(
                        role_arn=role_arn,
                        region="us-west-2",
                        external_id="test-external-id",
                        role_session_name="ComprehensiveTestSession",
                    )
                    assert credentials == mock_aiorefreshable_credentials

    @pytest.mark.asyncio
    async def test_get_session_with_all_parameters(
        self, role_arn: str, mock_aiorefreshable_credentials: Any
    ) -> None:
        """Test get_session with all parameters provided."""
        provider = AssumeRoleProvider()

        with patch.object(
            provider, "get_credentials", return_value=mock_aiorefreshable_credentials
        ):
            with patch(
                "aws.auth.providers.assume_role_provider.AioSession"
            ) as mock_session_class:
                mock_session = MagicMock()
                mock_session_class.return_value = mock_session

                session = await provider.get_session(
                    role_arn=role_arn,
                    region="us-west-2",
                    external_id="test-external-id",
                    role_session_name="SessionTest",
                )
                assert session == mock_session
                assert hasattr(session, "_credentials")
                assert session._credentials == mock_aiorefreshable_credentials

    @pytest.mark.asyncio
    async def test_get_credentials_sts_client_creation_failure(
        self, role_arn: str
    ) -> None:
        """Test get_credentials handles STS client creation failure."""
        provider = AssumeRoleProvider()

        with patch.object(provider, "aws_client_factory_session") as mock_session:
            mock_session.create_client.side_effect = Exception(
                "STS client creation failed"
            )

            with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
                await provider.get_credentials(
                    role_arn=role_arn,
                    region="us-west-2",
                )
