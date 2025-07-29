import pytest
from unittest.mock import patch, AsyncMock
from typing import Any, Dict, AsyncGenerator
from port_ocean.context.ocean import ocean

from aws.auth.session_factory import ResyncStrategyFactory, get_all_account_sessions
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.web_identity_provider import WebIdentityCredentialProvider

from tests.conftest import (
    AWS_TEST_ACCOUNT_ID,
    AWS_TEST_ACCOUNT_ID_2,
    AWS_TEST_ROLE_ARN_2,
)


class TestResyncStrategyFactory:
    """Test ResyncStrategyFactory strategy selection logic."""

    @pytest.mark.parametrize(
        "config,expected_strategy,expected_provider",
        [
            ({}, SingleAccountStrategy, StaticCredentialProvider),
            (None, SingleAccountStrategy, StaticCredentialProvider),
            ({"account_role_arn": []}, SingleAccountStrategy, StaticCredentialProvider),
        ],
    )
    @pytest.mark.asyncio
    async def test_factory_handles_edge_cases(
        self, config: Any, expected_strategy: Any, expected_provider: Any
    ) -> None:
        """Test factory handles various edge cases gracefully."""
        # Arrange
        ocean.app.config.integration.config = config

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert isinstance(strategy, expected_strategy)
        assert isinstance(strategy.provider, expected_provider)

    @pytest.mark.asyncio
    async def test_factory_strategy_selection_single_account(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        """Test factory selects SingleAccountStrategy for static credentials."""
        # Arrange
        ocean.app.config.integration.config = aws_credentials

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert isinstance(strategy, SingleAccountStrategy)
        assert callable(strategy.get_account_sessions)
        assert callable(strategy.healthcheck)

    @pytest.mark.asyncio
    async def test_factory_strategy_selection_multi_account(
        self, multi_account_config: Dict[str, Any]
    ) -> None:
        """Test factory selects MultiAccountStrategy for role ARN configuration."""
        # Arrange
        ocean.app.config.integration.config = multi_account_config

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert isinstance(strategy, MultiAccountStrategy)
        assert callable(strategy.get_account_sessions)
        assert callable(strategy.healthcheck)

    @pytest.mark.asyncio
    async def test_factory_strategy_selection_oidc(
        self, oidc_config: Dict[str, Any]
    ) -> None:
        """Test factory selects MultiAccountStrategy for OIDC configuration."""
        # Arrange
        ocean.app.config.integration.config = oidc_config

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert isinstance(strategy, MultiAccountStrategy)
        assert callable(strategy.get_account_sessions)
        assert callable(strategy.healthcheck)

    @pytest.mark.asyncio
    async def test_factory_caching_behavior(
        self, aws_credentials: Dict[str, str]
    ) -> None:
        """Test that factory caches strategy instances correctly."""
        # Arrange
        ocean.app.config.integration.config = aws_credentials

        # Act
        strategy1 = await ResyncStrategyFactory.create()
        strategy2 = await ResyncStrategyFactory.create()

        # Assert
        assert strategy1 is strategy2
        assert strategy1.config == strategy2.config

    @pytest.mark.asyncio
    async def test_oidc_priority_over_multi_account(
        self, oidc_config: Dict[str, Any]
    ) -> None:
        """Test that OIDC takes priority over multi-account when both are present."""
        # Arrange
        config_with_both = {
            **oidc_config,
            "account_role_arn": oidc_config["account_role_arn"] + [AWS_TEST_ROLE_ARN_2],
        }
        ocean.app.config.integration.config = config_with_both

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert isinstance(strategy, MultiAccountStrategy)
        assert isinstance(strategy.provider, WebIdentityCredentialProvider)
        assert callable(strategy.provider.get_credentials)
        assert callable(strategy.provider.get_session)

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_returns_valid_data(
        self, aws_credentials: Any
    ) -> None:
        """Test that get_all_account_sessions returns valid account sessions."""
        # Arrange
        ocean.app.config.integration.config = aws_credentials

        mock_strategy = AsyncMock()
        mock_session = AsyncMock()
        mock_account_info = {"Id": AWS_TEST_ACCOUNT_ID, "Name": "Test Account"}

        async def mock_get_account_sessions() -> (
            AsyncGenerator[tuple[Dict[str, Any], Any], None]
        ):
            yield mock_account_info, mock_session

        mock_strategy.get_account_sessions = mock_get_account_sessions

        with patch.object(ResyncStrategyFactory, "create", return_value=mock_strategy):
            # Act
            sessions = []
            async for account_info, session in get_all_account_sessions():
                sessions.append((account_info, session))

            # Assert
            assert len(sessions) > 0
            for account_info, session in sessions:
                assert "Id" in account_info
                assert "Name" in account_info
                assert session is not None

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_converts_to_account_info(
        self, aws_credentials: Any
    ) -> None:
        """Test that get_all_account_sessions converts raw account info to AccountInfo TypedDict."""
        # Arrange
        ocean.app.config.integration.config = aws_credentials

        mock_strategy = AsyncMock()
        mock_session = AsyncMock()
        raw_account_info = {"Id": AWS_TEST_ACCOUNT_ID_2, "Name": "Test Account"}

        async def mock_get_account_sessions() -> (
            AsyncGenerator[tuple[Dict[str, Any], Any], None]
        ):
            yield raw_account_info, mock_session

        mock_strategy.get_account_sessions = mock_get_account_sessions

        with patch.object(ResyncStrategyFactory, "create", return_value=mock_strategy):
            # Act
            sessions = []
            async for account_info, session in get_all_account_sessions():
                sessions.append((account_info, session))

            # Assert
            assert len(sessions) == 1
            account_info, session = sessions[0]
            assert isinstance(account_info, dict)
            assert account_info["Id"] == AWS_TEST_ACCOUNT_ID_2
            assert account_info["Name"] == "Test Account"
            assert session == mock_session

    @pytest.mark.asyncio
    async def test_creates_multi_account_strategy_with_string_account_role_arn(
        self, role_arn: str
    ) -> None:
        """Test factory creates MultiAccountStrategy when account_role_arn is a string."""
        # Arrange
        config = {"account_role_arn": role_arn}
        ocean.app.config.integration.config = config

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert isinstance(strategy, MultiAccountStrategy)
        assert isinstance(strategy.provider, AssumeRoleProvider)

    @pytest.mark.asyncio
    async def test_factory_creates_functional_strategies(
        self, multi_account_config: Any
    ) -> None:
        """Test that factory creates strategies that can actually work."""
        # Arrange
        ocean.app.config.integration.config = multi_account_config

        # Act
        strategy = await ResyncStrategyFactory.create()

        # Assert
        assert callable(strategy.get_account_sessions)
        assert callable(strategy.healthcheck)
        assert strategy.config == multi_account_config
        assert callable(strategy.provider.get_credentials)
        assert callable(strategy.provider.get_session)
