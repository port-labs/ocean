import pytest
from typing import Any
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.utils import AWSSessionError
from unittest.mock import patch

# Import constants from conftest
from tests.conftest import AWS_TEST_ACCOUNT_ID


class TestSingleAccountStrategy:
    """Test SingleAccountStrategy behavior."""

    def test_initialization(self) -> None:
        """Test strategy initializes with provider and config."""
        provider = StaticCredentialProvider()
        config = {"test_key": "test_value"}
        strategy = SingleAccountStrategy(provider=provider, config=config)

        assert strategy.provider == provider
        assert strategy.config == config
        assert strategy._session is None
        assert strategy.account_id is None

    @pytest.mark.asyncio
    async def test_healthcheck_success_with_valid_credentials(
        self, aws_credentials: Any, mock_session_with_sts: Any
    ) -> None:
        """Test successful healthcheck with valid credentials."""
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            result = await strategy.healthcheck()

            assert result is True
            assert strategy.account_id == AWS_TEST_ACCOUNT_ID
            assert strategy._session == mock_session_with_sts

            # Verify get_session was called with correct credentials from config
            mock_get_session.assert_called_with(
                aws_access_key_id="test_access_key",
                aws_secret_access_key="test_secret_key",
                aws_session_token="test_session_token",
            )

    @pytest.mark.asyncio
    async def test_healthcheck_fails_without_credentials(self) -> None:
        """Test healthcheck fails when credentials are missing."""
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config={})

        with pytest.raises(AWSSessionError, match="Single account is not accessible"):
            await strategy.healthcheck()

    @pytest.mark.asyncio
    async def test_get_account_sessions_requires_healthcheck(self) -> None:
        """Test get_account_sessions fails without running healthcheck first."""
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config={})

        with pytest.raises(AWSSessionError, match="Single account is not accessible"):
            async for _ in strategy.get_account_sessions():
                pass

    @pytest.mark.asyncio
    async def test_get_account_sessions_success_after_healthcheck(
        self, aws_credentials: Any, mock_session_with_sts: Any
    ) -> None:
        """Test get_account_sessions yields account info and session after successful healthcheck."""
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            await strategy.healthcheck()

            sessions = []
            async for account_info, session in strategy.get_account_sessions():
                sessions.append((account_info, session))

            assert len(sessions) == 1
            account_info, session = sessions[0]
            assert account_info["Id"] == AWS_TEST_ACCOUNT_ID
            assert account_info["Name"] == f"Account {AWS_TEST_ACCOUNT_ID}"
            assert session == mock_session_with_sts

            # Verify get_session was called with correct credentials from config
            mock_get_session.assert_called_with(
                aws_access_key_id="test_access_key",
                aws_secret_access_key="test_secret_key",
                aws_session_token="test_session_token",
            )

    @pytest.mark.asyncio
    async def test_healthcheck_with_credentials_vs_without(
        self, aws_credentials: Any, mock_session_with_sts: Any
    ) -> None:
        """Test healthcheck behavior with and without explicit credentials."""
        provider = StaticCredentialProvider()

        # Test with credentials in config
        strategy_with_creds = SingleAccountStrategy(
            provider=provider, config=aws_credentials
        )
        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts
            await strategy_with_creds.healthcheck()
            assert strategy_with_creds.account_id == AWS_TEST_ACCOUNT_ID

        # Test without credentials in config
        strategy_without_creds = SingleAccountStrategy(provider=provider, config={})
        with pytest.raises(AWSSessionError, match="Single account is not accessible"):
            await strategy_without_creds.healthcheck()
        assert strategy_without_creds.account_id is None

    @pytest.mark.asyncio
    async def test_healthcheck_session_creation_failure(
        self, aws_credentials: Any
    ) -> None:
        """Test healthcheck fails when session creation fails."""
        provider = StaticCredentialProvider()
        strategy = SingleAccountStrategy(provider=provider, config=aws_credentials)

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Session creation failed")

            with pytest.raises(
                AWSSessionError, match="Single account is not accessible"
            ):
                await strategy.healthcheck()
