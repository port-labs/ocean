import pytest
from typing import Dict
from unittest.mock import patch, AsyncMock

from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.utils import AWSSessionError


class TestSingleAccountStrategy:
    """Test SingleAccountStrategy behavior."""

    def test_initialization(self, aws_credentials: Dict[str, str]) -> None:
        """Test strategy initialization."""
        # Arrange & Act
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        # Assert
        assert strategy.provider == provider
        assert strategy.config == aws_credentials
        assert strategy.account_id is None

    @pytest.mark.asyncio
    async def test_healthcheck_success_with_valid_credentials(
        self, aws_credentials: Dict[str, str], mock_session_with_sts_client: AsyncMock
    ) -> None:
        """Test successful healthcheck with valid credentials."""
        # Arrange
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(
            provider, "get_session", return_value=mock_session_with_sts_client
        ):
            # Act
            result = await strategy.healthcheck()

            # Assert
            assert result is True
            assert strategy.account_id is not None

            sessions = []
            async for account_info, session in strategy.get_account_sessions():
                sessions.append((account_info, session))

            assert len(sessions) == 1
            assert sessions[0][1] == mock_session_with_sts_client

    @pytest.mark.asyncio
    async def test_healthcheck_failure_with_invalid_credentials(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        """Test healthcheck failure with invalid credentials."""
        # Arrange
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(
            provider, "get_session", side_effect=Exception("Invalid credentials")
        ):
            # Act & Assert
            with pytest.raises(
                AWSSessionError, match="Single account is not accessible"
            ):
                await strategy.healthcheck()
            assert strategy.account_id is None

    @pytest.mark.asyncio
    async def test_get_account_sessions_success_after_healthcheck(
        self, aws_credentials: Dict[str, str], mock_session_with_sts_client: AsyncMock
    ) -> None:
        """Test get_account_sessions yields account info and session after successful healthcheck."""
        # Arrange
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(
            provider, "get_session", return_value=mock_session_with_sts_client
        ):
            # Act
            await strategy.healthcheck()

            sessions = []
            async for account_info, session in strategy.get_account_sessions():
                sessions.append((account_info, session))

            # Assert
            assert len(sessions) == 1
            account_info, session = sessions[0]
            assert "Id" in account_info
            assert "Name" in account_info
            assert session == mock_session_with_sts_client

    @pytest.mark.asyncio
    async def test_healthcheck_with_credentials_vs_without(
        self, aws_credentials: Dict[str, str], mock_session_with_sts_client: AsyncMock
    ) -> None:
        """Test healthcheck behavior with and without explicit credentials."""
        # Arrange
        provider = StaticCredentialProvider()

        strategy_with_creds = SingleAccountStrategy(
            provider=provider, config=aws_credentials
        )
        with patch.object(
            provider, "get_session", return_value=mock_session_with_sts_client
        ):
            # Act
            await strategy_with_creds.healthcheck()

            # Assert
            assert strategy_with_creds.account_id is not None

    @pytest.mark.asyncio
    async def test_healthcheck_session_creation_failure(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        """Test healthcheck fails when session creation fails."""
        # Arrange
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(
            provider, "get_session", side_effect=Exception("Session creation failed")
        ):
            # Act & Assert
            with pytest.raises(
                AWSSessionError, match="Single account is not accessible"
            ):
                await strategy.healthcheck()
