import pytest
from unittest.mock import patch, MagicMock
from typing import Dict
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials

from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.utils import CredentialsProviderError


class TestStaticCredentialProvider:
    def test_is_refreshable_property(self) -> None:
        """Test that StaticCredentialProvider is not refreshable."""
        provider = StaticCredentialProvider()
        assert provider.is_refreshable is False

    @pytest.mark.asyncio
    async def test_get_credentials_with_valid_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            credentials = await provider.get_credentials(
                aws_access_key_id=aws_credentials["aws_access_key_id"],
                aws_secret_access_key=aws_credentials["aws_secret_access_key"],
                aws_session_token=aws_credentials["aws_session_token"],
            )
            assert isinstance(credentials, AioCredentials)
            assert credentials.access_key == aws_credentials["aws_access_key_id"]
            assert credentials.secret_key == aws_credentials["aws_secret_access_key"]
            assert credentials.token == aws_credentials["aws_session_token"]

    @pytest.mark.asyncio
    async def test_get_credentials_without_credentials(self) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_credentials()

    @pytest.mark.asyncio
    async def test_get_credentials_with_partial_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_credentials(
                    aws_access_key_id=aws_credentials["aws_access_key_id"]
                )
            with pytest.raises(CredentialsProviderError):
                await provider.get_credentials(
                    aws_secret_access_key=aws_credentials["aws_secret_access_key"]
                )

    @pytest.mark.asyncio
    async def test_get_session_with_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            session = await provider.get_session(
                aws_access_key_id=aws_credentials["aws_access_key_id"],
                aws_secret_access_key=aws_credentials["aws_secret_access_key"],
                aws_session_token=aws_credentials["aws_session_token"],
            )
            assert isinstance(session, AioSession)
            assert hasattr(session, "_credentials")
            assert (
                session._credentials.access_key == aws_credentials["aws_access_key_id"]
            )
            assert (
                session._credentials.secret_key
                == aws_credentials["aws_secret_access_key"]
            )
            assert session._credentials.token == aws_credentials["aws_session_token"]

    @pytest.mark.asyncio
    async def test_get_session_without_credentials(self) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_session()

    @pytest.mark.asyncio
    async def test_get_session_with_partial_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_session(
                    aws_access_key_id=aws_credentials["aws_access_key_id"]
                )

    @pytest.mark.asyncio
    async def test_get_credentials_with_only_access_key(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_credentials(
                    aws_access_key_id=aws_credentials["aws_access_key_id"]
                )

    @pytest.mark.asyncio
    async def test_get_credentials_with_only_secret_key(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_credentials(
                    aws_secret_access_key=aws_credentials["aws_secret_access_key"]
                )

    @pytest.mark.asyncio
    async def test_get_session_with_only_access_key(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_session(
                    aws_access_key_id=aws_credentials["aws_access_key_id"]
                )

    @pytest.mark.asyncio
    async def test_get_session_with_only_secret_key(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            with pytest.raises(CredentialsProviderError):
                await provider.get_session(
                    aws_secret_access_key=aws_credentials["aws_secret_access_key"]
                )

    def test_initialization_with_config(self) -> None:
        """Test provider initialization with config."""
        config = {"test_key": "test_value"}
        provider = StaticCredentialProvider(config=config)
        assert provider.config == config

    def test_initialization_without_config(self) -> None:
        """Test provider initialization without config."""
        provider = StaticCredentialProvider()
        assert provider.config == {}

    @pytest.mark.asyncio
    async def test_get_credentials_with_all_optional_parameters(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        """Test credential retrieval with all optional parameters."""
        with patch("aws.auth.providers.base.AioSession") as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            provider = StaticCredentialProvider()
            credentials = await provider.get_credentials(
                aws_access_key_id=aws_credentials["aws_access_key_id"],
                aws_secret_access_key=aws_credentials["aws_secret_access_key"],
                aws_session_token=aws_credentials["aws_session_token"],
            )
            assert isinstance(credentials, AioCredentials)
            assert credentials.access_key == aws_credentials["aws_access_key_id"]
            assert credentials.secret_key == aws_credentials["aws_secret_access_key"]
            assert credentials.token == aws_credentials["aws_session_token"]
