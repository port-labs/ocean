import pytest
from unittest.mock import MagicMock, patch
from unittest.mock import AsyncMock
from typing import Generator

from aws.auth.session_factory import ResyncStrategyFactory, get_all_account_sessions
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.strategies.organizations_strategy import OrganizationsStrategy

from aws.auth.utils import AWSSessionError


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
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
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
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)

    @pytest.mark.asyncio
    async def test_create_caches_strategy(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test create caches the strategy for subsequent calls."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
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
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
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
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config

            with patch.object(MultiAccountStrategy, "healthcheck") as mock_healthcheck:
                await ResyncStrategyFactory.create()
                mock_healthcheck.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_single_account_healthcheck_failure(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test create handles healthcheck failure for single account."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
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
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = {}

            with patch.object(
                SingleAccountStrategy, "healthcheck", new_callable=AsyncMock
            ) as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()
                with pytest.raises(AWSSessionError):
                    async for _ in strategy.get_account_sessions():
                        break
                assert isinstance(strategy, SingleAccountStrategy)
                assert isinstance(strategy.provider, AssumeRoleProvider)
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_none_config(self) -> None:
        """Test create handles None config."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = None

            with patch.object(
                SingleAccountStrategy, "healthcheck", new_callable=AsyncMock
            ) as mock_healthcheck:
                strategy = await ResyncStrategyFactory.create()
                with pytest.raises(AWSSessionError):
                    async for _ in strategy.get_account_sessions():
                        break
                assert isinstance(strategy, SingleAccountStrategy)
                assert isinstance(strategy.provider, AssumeRoleProvider)
                mock_healthcheck.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_mixed_config(self) -> None:
        """Test create handles config with both single and multi account settings."""
        mixed_config = {
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret_key",
            "account_role_arns": ["arn:aws:iam::123456789012:role/test-role"],
        }

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mixed_config

            strategy = await ResyncStrategyFactory.create()

            # Should prioritize multi-account when account_role_arns is present
            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, StaticCredentialProvider)

    @pytest.mark.asyncio
    async def test_create_with_string_account_role_arn(self) -> None:
        """Test create handles config with string accountRoleArn (should prioritize organizations strategy)."""
        string_config = {
            "aws_access_key_id": "test_access_key",
            "aws_secret_access_key": "test_secret_key",
            "account_role_arn": "arn:aws:iam::123456789012:role/test-role",
        }

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = string_config

            strategy = await ResyncStrategyFactory.create()

            # Should prioritize organizations strategy when single string ARN is provided
            assert isinstance(strategy, OrganizationsStrategy)
            assert isinstance(strategy.provider, StaticCredentialProvider)


class TestGetAllAccountSessions:
    """Test get_all_account_sessions function."""

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_single_account(
        self, mock_single_account_config: dict[str, object], mock_aiosession: AsyncMock
    ) -> None:
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
        self, mock_aiosession: AsyncMock
    ) -> None:
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
    async def test_get_all_account_sessions_empty(self) -> None:
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
        self, mock_single_account_config: dict[str, object]
    ) -> None:
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
        self, mock_aiosession: AsyncMock
    ) -> None:
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

    @pytest.mark.asyncio
    async def test_get_account_sessions_single_account_success(
        self, mock_single_account_config: dict[str, object]
    ) -> None:
        """Test get_account_sessions yields correct account info and session for single account (real path, not patched healthcheck)."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_single_account_config
            with patch.object(
                StaticCredentialProvider, "get_session", new_callable=AsyncMock
            ) as mock_get_session:
                mock_session = AsyncMock()
                mock_sts_client = AsyncMock()
                mock_sts_client.get_caller_identity.return_value = {
                    "Account": "123456789012"
                }
                # Use MagicMock for create_client and set up async context manager
                mock_session.create_client = MagicMock()
                mock_context_manager = AsyncMock()
                mock_context_manager.__aenter__.return_value = mock_sts_client
                mock_session.create_client.return_value = mock_context_manager
                mock_get_session.return_value = mock_session

                async def fake_healthcheck(self: SingleAccountStrategy) -> bool:
                    self._session = mock_session
                    self.account_id = "123456789012"
                    return True

                with patch.object(
                    SingleAccountStrategy, "healthcheck", new=fake_healthcheck
                ):
                    with patch(
                        "aws.auth.session_factory.ResyncStrategyFactory.create",
                        new=AsyncMock(
                            return_value=SingleAccountStrategy(
                                StaticCredentialProvider(), mock_single_account_config
                            )
                        ),
                    ):
                        strategy = await ResyncStrategyFactory.create()
                        sessions = []
                        async for (
                            account_info,
                            session,
                        ) in strategy.get_account_sessions():
                            sessions.append((account_info, session))
                        assert len(sessions) == 1
                        assert sessions[0][0]["Id"] == "123456789012"
                        assert sessions[0][0]["Name"] == "Account 123456789012"
                        assert sessions[0][1] == mock_session

    @pytest.mark.asyncio
    async def test_get_account_sessions_multi_account_success(
        self, mock_multi_account_config: dict[str, object]
    ) -> None:
        """Test get_account_sessions yields correct account info and session for multi account (real path, not patched healthcheck)."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = mock_multi_account_config
            with patch.object(
                AssumeRoleProvider, "get_session", new_callable=AsyncMock
            ) as mock_get_session:
                # Simulate two accounts
                mock_session_1 = AsyncMock()
                mock_session_2 = AsyncMock()
                mock_get_session.side_effect = [mock_session_1, mock_session_2]

                async def fake_healthcheck(self: MultiAccountStrategy) -> bool:
                    self._valid_arns = [
                        "arn:aws:iam::123456789012:role/test-role-1",
                        "arn:aws:iam::987654321098:role/test-role-2",
                    ]
                    self._valid_sessions = {
                        "arn:aws:iam::123456789012:role/test-role-1": mock_session_1,
                        "arn:aws:iam::987654321098:role/test-role-2": mock_session_2,
                    }
                    return True

                with patch.object(
                    MultiAccountStrategy, "healthcheck", new=fake_healthcheck
                ):
                    with patch(
                        "aws.auth.session_factory.ResyncStrategyFactory.create",
                        new=AsyncMock(
                            return_value=MultiAccountStrategy(
                                AssumeRoleProvider(), mock_multi_account_config
                            )
                        ),
                    ):
                        strategy = await ResyncStrategyFactory.create()
                        sessions = []
                        async for (
                            account_info,
                            session,
                        ) in strategy.get_account_sessions():
                            sessions.append((account_info, session))
                        assert len(sessions) == 2
                        assert sessions[0][0]["Id"] == "123456789012"
                        assert sessions[1][0]["Id"] == "987654321098"
                        assert sessions[0][1] == mock_session_1
                        assert sessions[1][1] == mock_session_2


@pytest.fixture
def mock_multi_account_config() -> dict[str, object]:
    """Mocks multi-account AWS configuration."""
    return {
        "account_role_arns": [
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        ],
        "region": "us-west-2",
        "external_id": "test-external-id",
    }


@pytest.fixture
def mock_single_account_config() -> dict[str, object]:
    """Mocks single account AWS configuration."""
    return {
        "aws_access_key_id": "test_access_key",
        "aws_secret_access_key": "test_secret_key",
        "aws_session_token": "test_session_token",
        "region": "us-west-2",
    }
