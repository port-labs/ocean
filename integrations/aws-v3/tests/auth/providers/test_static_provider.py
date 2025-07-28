import pytest
from unittest.mock import MagicMock
from typing import Dict
from aiobotocore.session import AioSession
from aiobotocore.credentials import AioCredentials

from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.utils import CredentialsProviderError


class TestStaticCredentialProvider:
    def test_is_refreshable_property(self) -> None:
        """Test that StaticCredentialProvider is not refreshable."""
        # Arrange
        provider = StaticCredentialProvider()

        # Act & Assert
        assert provider.is_refreshable is False

    @pytest.mark.asyncio
    async def test_get_credentials_with_valid_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        # Arrange
        provider = StaticCredentialProvider()

        # Act
        credentials = await provider.get_credentials(
            aws_access_key_id=aws_credentials["aws_access_key_id"],
            aws_secret_access_key=aws_credentials["aws_secret_access_key"],
            aws_session_token=aws_credentials["aws_session_token"],
        )

        # Assert
        assert isinstance(credentials, AioCredentials)
        assert credentials.access_key == aws_credentials["aws_access_key_id"]
        assert credentials.secret_key == aws_credentials["aws_secret_access_key"]
        assert credentials.token == aws_credentials["aws_session_token"]

    @pytest.mark.asyncio
    async def test_get_credentials_without_credentials(self) -> None:
        # Arrange
        provider = StaticCredentialProvider()

        # Act & Assert
        with pytest.raises(CredentialsProviderError):
            await provider.get_credentials()

    @pytest.mark.asyncio
    async def test_get_credentials_with_partial_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        # Arrange
        provider = StaticCredentialProvider()

        # Act & Assert
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
        self, aws_credentials: Dict[str, str], mock_aio_session: MagicMock
    ) -> None:
        # Arrange
        provider = StaticCredentialProvider()

        # Act
        session = await provider.get_session(
            aws_access_key_id=aws_credentials["aws_access_key_id"],
            aws_secret_access_key=aws_credentials["aws_secret_access_key"],
            aws_session_token=aws_credentials["aws_session_token"],
        )

        # Assert
        assert isinstance(session, AioSession)
        assert hasattr(session, "_credentials")
        assert session._credentials.access_key == aws_credentials["aws_access_key_id"]
        assert (
            session._credentials.secret_key == aws_credentials["aws_secret_access_key"]
        )
        assert session._credentials.token == aws_credentials["aws_session_token"]

    @pytest.mark.asyncio
    async def test_get_session_without_credentials(self) -> None:
        # Arrange
        provider = StaticCredentialProvider()

        # Act & Assert
        with pytest.raises(CredentialsProviderError):
            await provider.get_session()

    @pytest.mark.asyncio
    async def test_get_session_with_partial_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        # Arrange
        provider = StaticCredentialProvider()

        # Act & Assert
        with pytest.raises(CredentialsProviderError):
            await provider.get_session(
                aws_access_key_id=aws_credentials["aws_access_key_id"]
            )
