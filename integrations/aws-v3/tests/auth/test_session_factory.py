import pytest
from unittest.mock import MagicMock, patch
from unittest.mock import AsyncMock
from typing import Generator

from aws.auth.factory import ResyncStrategyFactory, get_all_account_sessions
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_credentials_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider

from aws.auth._helpers.exceptions import AWSSessionError


class TestResyncStrategyFactory:
    """Test ResyncStrategyFactory."""

    @pytest.fixture(autouse=True)
    def reset_cached_strategy(self) -> Generator[None, None, None]:
        """Reset the cached strategy by clearing the class variable."""
        ResyncStrategyFactory._cached_strategy = None
        yield

    @pytest.mark.asyncio
    async def test_create_single_account_strategy(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test create returns SingleAccountStrategy for single account config."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(
                SingleAccountStrategy, "healthcheck", new_callable=AsyncMock
            ) as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()
                assert isinstance(strategy, SingleAccountStrategy)
                assert isinstance(strategy.provider, StaticCredentialProvider)
                with pytest.raises(AWSSessionError):
                    async for _ in strategy.get_account_sessions():
                        break
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multi_account_strategy(
        self, mock_multi_account_config: dict[str, object]
    ) -> None:
        """Test create returns MultiAccountStrategy for multi account config."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)

    @pytest.mark.asyncio
    async def test_create_caches_strategy(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test create caches the strategy for subsequent calls."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(
                SingleAccountStrategy, "healthcheck", new_callable=AsyncMock
            ) as mock_healthcheck:
                # First call should create new strategy
                strategy1 = await ResyncStrategyFactory.create()
                with pytest.raises(AWSSessionError):
                    async for _ in strategy1.get_account_sessions():
                        break
                # Second call should return cached strategy
                strategy2 = await ResyncStrategyFactory.create()
                with pytest.raises(AWSSessionError):
                    async for _ in strategy2.get_account_sessions():
                        break
                assert strategy1 is strategy2
                # Health check should be called twice (once for each get_account_sessions)
                assert mock_healthcheck.call_count == 2

    @pytest.mark.asyncio
    async def test_create_single_account_performs_healthcheck(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test create performs healthcheck for single account strategy."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(
                SingleAccountStrategy, "healthcheck", new_callable=AsyncMock
            ) as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()
                with pytest.raises(AWSSessionError):
                    async for _ in strategy.get_account_sessions():
                        break
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_multi_account_no_healthcheck(
        self, mock_multi_account_config: dict[str, object]
    ) -> None:
        """Test create does not perform healthcheck for multi account strategy."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            with patch.object(MultiAccountStrategy, "healthcheck") as mock_healthcheck:
                await ResyncStrategyFactory.create()
                mock_healthcheck.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_single_account_healthcheck_failure(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test create handles healthcheck failure for single account."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            with patch.object(
                SingleAccountStrategy,
                "healthcheck",
                side_effect=Exception("Health check failed"),
            ):
                strategy = await ResyncStrategyFactory.create()
                # Do not set _session or account_id here, so healthcheck is called and fails
                with pytest.raises(Exception, match="Health check failed"):
                    async for _ in strategy.get_account_sessions():
                        break

    @pytest.mark.asyncio
    async def test_create_with_empty_config(self) -> None:
        """Test create handles empty config."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = {}

            with pytest.raises(Exception, match="Unable to create a resync strategy"):
                await ResyncStrategyFactory.create()

    @pytest.mark.asyncio
    async def test_create_with_none_config(self) -> None:
        """Test create handles None config."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = None

            with pytest.raises(Exception, match="Unable to create a resync strategy"):
                await ResyncStrategyFactory.create()

    @pytest.mark.asyncio
    async def test_create_with_mixed_config(self) -> None:
        """Test create handles config with both single and multi account settings."""
        mixed_config = {
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret_key",
            "account_role_arn": ["arn:aws:iam::123456789012:role/test-role"],
        }

        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mixed_config

            strategy = await ResyncStrategyFactory.create()

            # Should prioritize multi-account when account_role_arn is present
            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)


class TestGetAllAccountSessions:
    """Test get_all_account_sessions function."""

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_single_account(
        self, mock_single_account_config: dict[str, object], mock_aiosession: AsyncMock
    ) -> None:
        """Test get_all_account_sessions with single account strategy."""
        with patch("aws.auth.factory.ResyncStrategyFactory.create") as mock_create:
            mock_strategy = MagicMock(spec=SingleAccountStrategy)
            # Create proper AccountContext objects instead of tuples
            mock_account_context = {
                "details": {"Id": "123456789012", "Name": "Account 123456789012"},
                "session": mock_aiosession,
            }
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = [
                mock_account_context
            ]
            mock_create.return_value = mock_strategy

            accounts = []
            async for account_context in get_all_account_sessions():
                accounts.append(account_context)

            assert len(accounts) == 1
            account_context = accounts[0]
            assert account_context["details"]["Id"] == "123456789012"
            assert account_context["details"]["Name"] == "Account 123456789012"
            assert account_context["session"] == mock_aiosession

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_multi_account(
        self, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_all_account_sessions with multi account strategy."""
        with patch("aws.auth.factory.ResyncStrategyFactory.create") as mock_create:
            mock_strategy = MagicMock(spec=MultiAccountStrategy)
            # Create proper AccountContext objects instead of tuples
            mock_account_contexts = [
                {
                    "details": {"Id": "123456789012", "Name": "Account 123456789012"},
                    "session": mock_aiosession,
                },
                {
                    "details": {"Id": "987654321098", "Name": "Account 987654321098"},
                    "session": mock_aiosession,
                },
            ]
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = (
                mock_account_contexts
            )
            mock_create.return_value = mock_strategy

            accounts = []
            async for account_info in get_all_account_sessions():
                accounts.append(account_info)

            assert len(accounts) == 2
            assert accounts[0]["details"]["Id"] == "123456789012"
            assert accounts[1]["details"]["Id"] == "987654321098"

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_empty(self) -> None:
        """Test get_all_account_sessions with no accounts."""
        with patch("aws.auth.factory.ResyncStrategyFactory.create") as mock_create:
            mock_strategy = MagicMock(spec=SingleAccountStrategy)
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = []
            mock_create.return_value = mock_strategy

            accounts = []
            async for account_info in get_all_account_sessions():
                accounts.append(account_info)

            assert len(accounts) == 0

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_strategy_error(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test get_all_account_sessions handles strategy creation error."""
        with patch("aws.auth.factory.ResyncStrategyFactory.create") as mock_create:
            mock_create.side_effect = Exception("Strategy creation failed")

            with pytest.raises(Exception, match="Strategy creation failed"):
                async for _ in get_all_account_sessions():
                    break

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_yields_correct_types(
        self, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_all_account_sessions yields correct types."""
        with patch("aws.auth.factory.ResyncStrategyFactory.create") as mock_create:
            mock_strategy = MagicMock(spec=SingleAccountStrategy)
            mock_account_context = {
                "details": {"Id": "123456789012", "Name": "Account 123456789012"},
                "session": mock_aiosession,
            }
            mock_strategy.get_account_sessions.return_value.__aiter__.return_value = [
                mock_account_context
            ]
            mock_create.return_value = mock_strategy

            async for account_context in get_all_account_sessions():
                # Check that account_info is a dict with required keys
                account_info = account_context["details"]
                assert isinstance(account_info, dict)
                assert "Id" in account_info
                assert "Name" in account_info
                assert account_context["session"] == mock_aiosession

    @pytest.mark.asyncio
    async def test_get_account_sessions_single_account_success(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test get_account_sessions for single account strategy."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config

            strategy = await ResyncStrategyFactory.create()
            # Mock the healthcheck to prevent real AWS calls
            with patch.object(strategy, "healthcheck", return_value=True):
                # Directly set the strategy attributes to simulate successful healthcheck
                if hasattr(strategy, "_session"):
                    strategy._session = MagicMock()
                if hasattr(strategy, "_identity"):
                    strategy._identity = {"Account": "123456789012"}

                sessions = []
                async for account_context in strategy.get_account_sessions():
                    sessions.append(account_context)

                assert len(sessions) == 1
                account_context = sessions[0]
                assert account_context["details"]["Id"] == "123456789012"
                assert account_context["details"]["Name"] == "Account 123456789012"

    @pytest.mark.asyncio
    async def test_get_account_sessions_multi_account_success(
        self, mock_multi_account_config: dict[str, object]
    ) -> None:
        """Test get_account_sessions for multi account strategy."""
        with patch("aws.auth.factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            strategy = await ResyncStrategyFactory.create()
            # Mock the healthcheck to prevent real AWS calls
            with patch.object(strategy, "healthcheck", return_value=True):
                # Directly set the strategy attributes to simulate successful healthcheck
                if hasattr(strategy, "_valid_arns"):
                    strategy._valid_arns = ["arn:aws:iam::123456789012:role/test-role"]
                if hasattr(strategy, "_valid_sessions"):
                    from aiobotocore.session import AioSession

                    strategy._valid_sessions = {
                        "arn:aws:iam::123456789012:role/test-role": MagicMock(
                            spec=AioSession
                        )
                    }

                sessions = []
                async for account_context in strategy.get_account_sessions():
                    sessions.append(account_context)

                assert len(sessions) == 1
                account_context = sessions[0]
                assert account_context["details"]["Id"] == "123456789012"
                assert account_context["details"]["Name"] == "Account 123456789012"


@pytest.fixture
def mock_multi_account_config() -> dict[str, object]:
    """Create a mock multi-account configuration."""
    return {
        "account_role_arn": ["arn:aws:iam::123456789012:role/test-role"],
        "region": "us-west-2",
        "external_id": "test-external-id",
    }


@pytest.fixture
def mock_single_account_config() -> dict[str, object]:
    """Create a mock single-account configuration."""
    return {
        "aws_access_key_id": "test_access_key",
        "aws_secret_access_key": "test_secret_key",
        "aws_session_token": "test_session_token",
        "region": "us-west-2",
        # Ensure no account_role_arn to force single account strategy
        "account_role_arn": None,
    }
