import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials, AioRefreshableCredentials

from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.assume_role_with_web_identity_provider import (
    AssumeRoleWithWebIdentityProvider,
)
from aws.auth.utils import CredentialsProviderError


def create_mock_sts_context_manager(mock_sts_client: MagicMock) -> MagicMock:
    """Helper function to create a mock STS context manager."""
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_sts_client)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    return mock_context_manager


class TestCredentialProviderBase:
    """Test the base CredentialProvider class."""

    def test_credential_provider_initialization(self) -> None:
        """Test CredentialProvider initialization with config."""
        config = {"test_key": "test_value"}
        provider = StaticCredentialProvider(config=config)
        assert provider.config == config
        assert provider.aws_client_factory_session is not None

    def test_credential_provider_initialization_empty_config(self) -> None:
        """Test CredentialProvider initialization with empty config."""
        provider = StaticCredentialProvider()
        assert provider.config == {}
        assert provider.aws_client_factory_session is not None


class TestStaticCredentialProvider:
    """Test StaticCredentialProvider."""

    def test_is_refreshable_property(self) -> None:
        """Test is_refreshable property returns False."""
        provider = StaticCredentialProvider()
        assert provider.is_refreshable is False

    @pytest.mark.asyncio
    async def test_get_credentials_with_valid_credentials(self) -> None:
        """Test get_credentials with valid access and secret keys."""
        provider = StaticCredentialProvider()
        credentials = await provider.get_credentials(
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key",
            aws_session_token="test_session_token",
        )
        assert isinstance(credentials, AioCredentials)
        assert credentials.access_key == "test_access_key"
        assert credentials.secret_key == "test_secret_key"
        assert credentials.token == "test_session_token"

    @pytest.mark.asyncio
    async def test_get_credentials_without_credentials(self) -> None:
        """Test get_credentials without explicit credentials (uses boto3 chain)."""
        provider = StaticCredentialProvider()
        credentials = await provider.get_credentials()
        assert credentials is None

    @pytest.mark.asyncio
    async def test_get_credentials_with_partial_credentials(self) -> None:
        """Test get_credentials with only access key (should return None)."""
        provider = StaticCredentialProvider()
        credentials = await provider.get_credentials(
            aws_access_key_id="test_access_key"
        )
        assert credentials is None

    @pytest.mark.asyncio
    async def test_get_session_with_credentials(self) -> None:
        """Test get_session with explicit credentials."""
        provider = StaticCredentialProvider()
        session = await provider.get_session(
            aws_access_key_id="test_access_key",
            aws_secret_access_key="test_secret_key",
            aws_session_token="test_session_token",
        )
        assert isinstance(session, AioSession)
        assert hasattr(session, "_credentials")
        assert session._credentials.access_key == "test_access_key"
        assert session._credentials.secret_key == "test_secret_key"
        assert session._credentials.token == "test_session_token"

    @pytest.mark.asyncio
    async def test_get_session_without_credentials(self) -> None:
        """Test get_session without explicit credentials."""
        provider = StaticCredentialProvider()
        session = await provider.get_session()
        assert isinstance(session, AioSession)
        # The session should be created but credentials should not be explicitly set by our provider
        # If _credentials exists, it should be None (not set by us)
        if hasattr(session, "_credentials"):
            assert session._credentials is None

    @pytest.mark.asyncio
    async def test_get_session_with_partial_credentials(self) -> None:
        """Test get_session with partial credentials (should not set _credentials)."""
        provider = StaticCredentialProvider()
        session = await provider.get_session(aws_access_key_id="test_access_key")
        assert isinstance(session, AioSession)
        if hasattr(session, "_credentials"):
            assert session._credentials is None


class TestAssumeRoleProvider:
    """Test AssumeRoleProvider."""

    def test_is_refreshable_property(self) -> None:
        """Test is_refreshable property returns True."""
        provider = AssumeRoleProvider()
        assert provider.is_refreshable is True

    @pytest.mark.asyncio
    async def test_get_credentials_success(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials successfully assumes role."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "assumed_access_key",
                "SecretAccessKey": "assumed_secret_key",
                "SessionToken": "assumed_session_token",
                "Expiration": "2024-12-31T23:59:59Z",
            }
        }
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )
                    assert credentials == mock_creds
                    mock_sts_client.assume_role.assert_not_called()  # Not called directly
                    mock_create_creds.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credentials_with_external_id(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials with external ID."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                        external_id="test-external-id",
                    )
                    assert credentials == mock_creds
                    mock_create_creds.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credentials_default_session_name(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials uses default session name when not provided."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )
                    assert credentials == mock_creds
                    mock_sts_client.assume_role.assert_not_called()  # Not called directly
                    mock_create_creds.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credentials_sts_client_error(self) -> None:
        """Test get_credentials handles STS client creation error."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_session.create_client.side_effect = Exception("STS client error")

        with patch.object(provider, "aws_client_factory_session", mock_session):
            with pytest.raises(CredentialsProviderError, match="Failed to assume role"):
                await provider.get_credentials(
                    role_arn="arn:aws:iam::123456789012:role/test-role",
                    region="us-west-2",
                )

    @pytest.mark.asyncio
    async def test_get_credentials_assume_role_error(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials handles assume role error."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_assume_role_refresher.side_effect = Exception("Assume role failed")
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with pytest.raises(
                    CredentialsProviderError, match="Failed to assume role"
                ):
                    await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )

    @pytest.mark.asyncio
    async def test_get_session_success(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_session successfully creates session with assumed role credentials."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    session = await provider.get_session(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )
                    assert isinstance(session, AioSession)
                    assert hasattr(session, "_credentials")
                    assert session._credentials == mock_creds

    @pytest.mark.asyncio
    async def test_get_session_missing_role_arn(self) -> None:
        """Test get_session raises error when role_arn is missing."""
        provider = AssumeRoleProvider()

        with pytest.raises(CredentialsProviderError, match="role_arn is required"):
            await provider.get_session(region="us-west-2")

    @pytest.mark.asyncio
    async def test_get_session_credentials_error(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_session handles credentials error."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_assume_role_refresher.side_effect = Exception("Assume role failed")
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with pytest.raises(
                    CredentialsProviderError, match="Failed to assume role"
                ):
                    await provider.get_session(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )

    @pytest.mark.asyncio
    async def test_get_credentials_with_custom_role_session_name(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials with custom role session name."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                        role_session_name="CustomTestSession",
                    )
                    assert credentials == mock_creds
                    mock_create_creds.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_credentials_with_different_regions(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials with different AWS regions."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)

        test_regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]

        for region in test_regions:
            with patch.object(provider, "aws_client_factory_session", mock_session):
                mock_session.create_client.return_value = mock_context_manager
                with patch(
                    "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                    side_effect=mock_assume_role_refresher.side_effect,
                ):
                    with patch(
                        "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                    ) as mock_create_creds:
                        mock_creds = MagicMock(spec=AioRefreshableCredentials)
                        mock_create_creds.return_value = mock_creds
                        credentials = await provider.get_credentials(
                            role_arn="arn:aws:iam::123456789012:role/test-role",
                            region=region,
                        )
                        assert credentials == mock_creds
                        # Verify the session was created with the correct region
                        mock_session.create_client.assert_called_with(
                            "sts", region_name=region
                        )

    @pytest.mark.asyncio
    async def test_get_credentials_refresh_behavior(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test that credentials are properly configured for refresh behavior."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )
                    assert credentials == mock_creds
                    # Verify AioRefreshableCredentials was created with correct parameters
                    mock_create_creds.assert_called_once()
                    call_args = mock_create_creds.call_args
                    assert call_args[1]["method"] == "sts-assume-role"
                    assert call_args[1]["refresh_using"] is not None

    @pytest.mark.asyncio
    async def test_get_credentials_with_all_optional_parameters(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_credentials with all optional parameters provided."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                        external_id="test-external-id",
                        role_session_name="ComprehensiveTestSession",
                    )
                    assert credentials == mock_creds
                    mock_create_creds.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_with_all_parameters(
        self, mock_assume_role_refresher: MagicMock
    ) -> None:
        """Test get_session with all parameters provided."""
        provider = AssumeRoleProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()
        mock_context_manager = create_mock_sts_context_manager(mock_sts_client)
        with patch.object(provider, "aws_client_factory_session", mock_session):
            mock_session.create_client.return_value = mock_context_manager
            with patch(
                "aws.auth.providers.assume_role_provider.create_assume_role_refresher",
                side_effect=mock_assume_role_refresher.side_effect,
            ):
                with patch(
                    "aws.auth.providers.assume_role_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds
                    session = await provider.get_session(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                        external_id="test-external-id",
                        role_session_name="SessionTest",
                    )
                    assert isinstance(session, AioSession)
                    assert hasattr(session, "_credentials")
                    assert session._credentials == mock_creds


class TestAssumeRoleWithWebIdentityProvider:
    """Test AssumeRoleWithWebIdentityProvider."""

    def test_is_refreshable_property(self) -> None:
        """Test is_refreshable property returns True."""
        provider = AssumeRoleWithWebIdentityProvider()
        assert provider.is_refreshable is True

    @patch.dict("os.environ", {"AWS_WEB_IDENTITY_TOKEN_FILE": "/tmp/test-token"})
    @patch("builtins.open", create=True)
    def test_read_web_identity_token_success(self, mock_open: MagicMock) -> None:
        """Test successful reading of web identity token."""
        provider = AssumeRoleWithWebIdentityProvider()
        mock_file = MagicMock()
        mock_file.read.return_value = "test-token-content\n"
        mock_open.return_value.__enter__.return_value = mock_file

        token = provider._read_web_identity_token()
        assert token == "test-token-content"
        mock_open.assert_called_once_with("/tmp/test-token", "r")

    def test_read_web_identity_token_missing_env_var(self) -> None:
        """Test error when AWS_WEB_IDENTITY_TOKEN_FILE is not set."""
        provider = AssumeRoleWithWebIdentityProvider()
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(CredentialsProviderError) as exc_info:
                provider._read_web_identity_token()
            assert (
                "AWS_WEB_IDENTITY_TOKEN_FILE environment variable is required"
                in str(exc_info.value)
            )

    @patch.dict("os.environ", {"AWS_WEB_IDENTITY_TOKEN_FILE": "/tmp/nonexistent"})
    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_read_web_identity_token_file_not_found(self, mock_open: MagicMock) -> None:
        """Test error when token file doesn't exist."""
        provider = AssumeRoleWithWebIdentityProvider()
        with pytest.raises(CredentialsProviderError) as exc_info:
            provider._read_web_identity_token()
        assert "Web identity token file /tmp/nonexistent not found" in str(
            exc_info.value
        )

    @patch.dict("os.environ", {"AWS_WEB_IDENTITY_TOKEN_FILE": "/tmp/empty-token"})
    @patch("builtins.open", create=True)
    def test_read_web_identity_token_empty_file(self, mock_open: MagicMock) -> None:
        """Test error when token file is empty."""
        provider = AssumeRoleWithWebIdentityProvider()
        mock_file = MagicMock()
        mock_file.read.return_value = ""
        mock_open.return_value.__enter__.return_value = mock_file

        with pytest.raises(CredentialsProviderError) as exc_info:
            provider._read_web_identity_token()
        assert "Web identity token file /tmp/empty-token is empty" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"AWS_WEB_IDENTITY_TOKEN_FILE": "/tmp/test-token"})
    async def test_get_credentials_success(self) -> None:
        """Test successful get_credentials with web identity."""
        provider = AssumeRoleWithWebIdentityProvider()
        mock_session = MagicMock()
        mock_sts_client = AsyncMock()

        # Mock the token file
        mock_file = MagicMock()
        mock_file.read.return_value = "test-web-identity-token"
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_file

            # Mock STS response
            mock_sts_client.assume_role_with_web_identity.return_value = {
                "Credentials": {
                    "AccessKeyId": "test_access_key",
                    "SecretAccessKey": "test_secret_key",
                    "SessionToken": "test_session_token",
                    "Expiration": MagicMock(),
                }
            }
            mock_sts_client.assume_role_with_web_identity.return_value["Credentials"][
                "Expiration"
            ].isoformat.return_value = "2024-12-31T23:59:59Z"

            mock_context_manager = create_mock_sts_context_manager(mock_sts_client)

            with patch.object(provider, "aws_client_factory_session", mock_session):
                mock_session.create_client.return_value = mock_context_manager

                with patch(
                    "aws.auth.providers.assume_role_with_web_identity_provider.AioRefreshableCredentials.create_from_metadata"
                ) as mock_create_creds:
                    mock_creds = MagicMock(spec=AioRefreshableCredentials)
                    mock_create_creds.return_value = mock_creds

                    credentials = await provider.get_credentials(
                        role_arn="arn:aws:iam::123456789012:role/test-role",
                        region="us-west-2",
                    )

                    assert credentials == mock_creds
                    mock_sts_client.assume_role_with_web_identity.assert_called_once()
                    call_args = mock_sts_client.assume_role_with_web_identity.call_args[
                        1
                    ]
                    assert (
                        call_args["RoleArn"]
                        == "arn:aws:iam::123456789012:role/test-role"
                    )
                    assert call_args["WebIdentityToken"] == "test-web-identity-token"
                    assert call_args["RoleSessionName"] == "OceanWebIdentitySession"
                    assert call_args["DurationSeconds"] == 3600
