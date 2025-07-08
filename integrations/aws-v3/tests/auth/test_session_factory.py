import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession

from aws.auth.session_factory import ResyncStrategyFactory, get_all_account_sessions
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider

import aws.auth.session_factory


class TestResyncStrategyFactory:
    """Test ResyncStrategyFactory."""

    @pytest.fixture(autouse=True)
    def reset_cached_strategy(self):
        """Reset the cached strategy by mocking the module variable."""
        with patch.object(aws.auth.session_factory, "_cached_strategy", None):
            yield

    @pytest.mark.asyncio
    async def test_create_single_account_strategy(self, mock_single_account_config):
        """Test create returns SingleAccountStrategy for single account config."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(SingleAccountStrategy, "healthcheck") as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()

                assert isinstance(strategy, SingleAccountStrategy)
                assert isinstance(strategy.provider, StaticCredentialProvider)
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multi_account_strategy(self, mock_multi_account_config):
        """Test create returns MultiAccountStrategy for multi account config."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)

    @pytest.mark.asyncio
    async def test_create_caches_strategy(self, mock_single_account_config):
        """Test create caches the strategy for subsequent calls."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(SingleAccountStrategy, "healthcheck") as mock_healthcheck:
                # First call should create new strategy
                strategy1 = await ResyncStrategyFactory.create()
                # Second call should return cached strategy
                strategy2 = await ResyncStrategyFactory.create()

                assert strategy1 is strategy2
                # Health check should only be called once (on first creation)
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_single_account_performs_healthcheck(
        self, mock_single_account_config
    ):
        """Test create performs healthcheck for single account strategy."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(SingleAccountStrategy, "healthcheck") as mock_healthcheck:
                await ResyncStrategyFactory.create()
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multi_account_no_healthcheck(self, mock_multi_account_config):
        """Test create does not perform healthcheck for multi account strategy."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            with patch.object(MultiAccountStrategy, "healthcheck") as mock_healthcheck:
                await ResyncStrategyFactory.create()
                mock_healthcheck.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_single_account_healthcheck_failure(
        self, mock_single_account_config
    ):
        """Test create handles healthcheck failure for single account."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(
                SingleAccountStrategy,
                "healthcheck",
                side_effect=Exception("Health check failed"),
            ):
                with pytest.raises(Exception, match="Health check failed"):
                    await ResyncStrategyFactory.create()

    @pytest.mark.asyncio
    async def test_create_with_empty_config(self):
        """Test create handles empty config."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = {}

            with patch.object(SingleAccountStrategy, "healthcheck") as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()

                assert isinstance(strategy, SingleAccountStrategy)
                assert isinstance(strategy.provider, StaticCredentialProvider)
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_none_config(self):
        """Test create handles None config."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = None

            with patch.object(SingleAccountStrategy, "healthcheck") as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()

                assert isinstance(strategy, SingleAccountStrategy)
                assert isinstance(strategy.provider, StaticCredentialProvider)
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_mixed_config(self):
        """Test create handles config with both single and multi account settings."""
        mixed_config = {
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret_key",
            "account_role_arn": ["arn:aws:iam::123456789012:role/test-role"],
        }

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mixed_config

            strategy = await ResyncStrategyFactory.create()

            # Should prioritize multi-account when account_role_arn is present
            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)


class TestGetAllAccountSessions:
    """Test get_all_account_sessions function."""

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_single_account(
        self, mock_single_account_config, mock_aiosession
    ):
        """Test get_all_account_sessions with single account strategy."""
        with patch(
            "aws.auth.session_factory.ResyncStrategyFactory.create"
        ) as mock_create:
            mock_strategy = MagicMock(spec=SingleAccountStrategy)
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = [
                (
                    {"Id": "123456789012", "Name": "Account 123456789012"},
                    mock_aiosession,
                )
            ]
            mock_create.return_value = mock_strategy

            sessions = []
            async for account_info, session in get_all_account_sessions():
                sessions.append((account_info, session))

            assert len(sessions) == 1
            account_info, session = sessions[0]
            assert account_info["Id"] == "123456789012"
            assert account_info["Name"] == "Account 123456789012"
            assert session == mock_aiosession

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_multi_account(
        self, mock_multi_account_config, mock_aiosession
    ):
        """Test get_all_account_sessions with multi account strategy."""
        with patch(
            "aws.auth.session_factory.ResyncStrategyFactory.create"
        ) as mock_create:
            mock_strategy = MagicMock(spec=MultiAccountStrategy)
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = [
                (
                    {"Id": "123456789012", "Name": "Account 123456789012"},
                    mock_aiosession,
                ),
                (
                    {"Id": "987654321098", "Name": "Account 987654321098"},
                    mock_aiosession,
                ),
            ]
            mock_create.return_value = mock_strategy

            sessions = []
            async for account_info, session in get_all_account_sessions():
                sessions.append((account_info, session))

            assert len(sessions) == 2
            assert sessions[0][0]["Id"] == "123456789012"
            assert sessions[1][0]["Id"] == "987654321098"

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_empty(self, mock_single_account_config):
        """Test get_all_account_sessions with no accounts."""
        with patch(
            "aws.auth.session_factory.ResyncStrategyFactory.create"
        ) as mock_create:
            mock_strategy = MagicMock(spec=SingleAccountStrategy)
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = []
            mock_create.return_value = mock_strategy

            sessions = []
            async for account_info, session in get_all_account_sessions():
                sessions.append((account_info, session))

            assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_strategy_error(
        self, mock_single_account_config
    ):
        """Test get_all_account_sessions handles strategy creation error."""
        with patch(
            "aws.auth.session_factory.ResyncStrategyFactory.create",
            side_effect=Exception("Strategy error"),
        ):
            with pytest.raises(Exception, match="Strategy error"):
                async for _ in get_all_account_sessions():
                    pass

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_yields_correct_types(
        self, mock_single_account_config, mock_aiosession
    ):
        """Test get_all_account_sessions yields correct types."""
        with patch(
            "aws.auth.session_factory.ResyncStrategyFactory.create"
        ) as mock_create:
            mock_strategy = MagicMock(spec=SingleAccountStrategy)
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = [
                (
                    {"Id": "123456789012", "Name": "Account 123456789012"},
                    mock_aiosession,
                )
            ]
            mock_create.return_value = mock_strategy

            async for account_info, session in get_all_account_sessions():
                # Check that account_info is a dict with required keys
                assert isinstance(account_info, dict)
                assert "Id" in account_info
                assert "Name" in account_info
                # Check that session is the expected mock session
                assert session == mock_aiosession
                break
