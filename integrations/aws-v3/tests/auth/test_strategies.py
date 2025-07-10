import pytest
from unittest.mock import AsyncMock, patch

from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.utils import AWSSessionError


class TestAWSSessionStrategyBase:
    """Test the base AWSSessionStrategy class."""

    def test_strategy_initialization(self) -> None:
        """Test AWSSessionStrategy initialization."""
        provider = StaticCredentialProvider()
        config = {"test_key": "test_value"}
        strategy = SingleAccountStrategy(provider=provider, config=config)
        assert strategy.provider == provider
        assert strategy.config == config


class TestSingleAccountStrategy:
    """Test SingleAccountStrategy."""

    @pytest.fixture
    def strategy(
        self, mock_single_account_config: dict[str, object]
    ) -> SingleAccountStrategy:
        """Create a SingleAccountStrategy instance."""
        provider = StaticCredentialProvider(config=mock_single_account_config)
        return SingleAccountStrategy(
            provider=provider, config=mock_single_account_config
        )

    @pytest.mark.asyncio
    async def test_get_account_sessions(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_account_sessions yields account info and session, expects error if account_id not set."""
        # Simulate missing account_id and session
        strategy._session = mock_aiosession
        if hasattr(strategy, "account_id"):
            delattr(strategy, "account_id")
        with pytest.raises(AttributeError):
            async for _ in strategy.get_account_sessions():
                pass

    @pytest.mark.asyncio
    async def test_get_account_sessions_with_account_id(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_account_sessions uses account_id when available."""
        strategy.account_id = "123456789012"
        strategy._session = mock_aiosession
        sessions = []
        async for account_info, session in strategy.get_account_sessions():
            sessions.append((account_info, session))

        assert len(sessions) == 1
        account_info, session = sessions[0]
        assert account_info["Id"] == "123456789012"
        assert account_info["Name"] == "Account 123456789012"
        assert session == mock_aiosession


class TestSingleAccountHealthCheckMixin:
    """Test SingleAccountHealthCheckMixin."""

    @pytest.fixture
    def strategy(
        self, mock_single_account_config: dict[str, object]
    ) -> SingleAccountStrategy:
        """Create a SingleAccountStrategy instance."""
        provider = StaticCredentialProvider(config=mock_single_account_config)
        return SingleAccountStrategy(
            provider=provider, config=mock_single_account_config
        )

    @pytest.mark.asyncio
    async def test_healthcheck_success(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds with valid credentials."""
        mock_sts_client = AsyncMock()
        mock_sts_client.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test-role/test-session",
            "UserId": "AIDACKCEVSQ6C2EXAMPLE",
        }

        with patch.object(mock_aiosession, "create_client") as mock_create_client:
            mock_create_client.return_value.__aenter__.return_value = mock_sts_client
            with patch.object(
                strategy.provider, "get_session", return_value=mock_aiosession
            ):
                result = await strategy.healthcheck()
                assert result is True
                assert strategy.account_id == "123456789012"

    @pytest.mark.asyncio
    async def test_healthcheck_without_credentials(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds without explicit credentials."""
        strategy.config = {}  # No credentials in config
        mock_sts_client = AsyncMock()
        mock_sts_client.get_caller_identity.return_value = {
            "Account": "123456789012",
        }

        with patch.object(mock_aiosession, "create_client") as mock_create_client:
            mock_create_client.return_value.__aenter__.return_value = mock_sts_client
            with patch.object(
                strategy.provider, "get_session", return_value=mock_aiosession
            ):
                result = await strategy.healthcheck()
                assert result is True
                assert strategy.account_id == "123456789012"

    @pytest.mark.asyncio
    async def test_healthcheck_sts_error(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck fails when STS call fails."""
        mock_sts_client = AsyncMock()
        mock_sts_client.get_caller_identity.side_effect = Exception("STS error")

        with patch.object(mock_aiosession, "create_client") as mock_create_client:
            mock_create_client.return_value.__aenter__.return_value = mock_sts_client
            with patch.object(
                strategy.provider, "get_session", return_value=mock_aiosession
            ):
                with pytest.raises(
                    AWSSessionError, match="Single account is not accessible"
                ):
                    await strategy.healthcheck()

    @pytest.mark.asyncio
    async def test_healthcheck_session_error(
        self, strategy: SingleAccountStrategy
    ) -> None:
        """Test healthcheck fails when session creation fails."""
        with patch.object(
            strategy.provider, "get_session", side_effect=Exception("Session error")
        ):
            with pytest.raises(
                AWSSessionError, match="Single account is not accessible"
            ):
                await strategy.healthcheck()


class TestMultiAccountStrategy:
    """Test MultiAccountStrategy."""

    @pytest.fixture
    def strategy(
        self, mock_multi_account_config: dict[str, object]
    ) -> MultiAccountStrategy:
        """Create a MultiAccountStrategy instance."""
        provider = AssumeRoleProvider(config=mock_multi_account_config)
        return MultiAccountStrategy(provider=provider, config=mock_multi_account_config)

    @pytest.mark.asyncio
    async def test_get_account_sessions_with_valid_sessions(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_account_sessions yields pre-validated sessions."""
        # Set up the strategy as if healthcheck has already been completed
        strategy._valid_arns = ["arn:aws:iam::123456789012:role/test-role"]
        strategy._valid_sessions = {
            "arn:aws:iam::123456789012:role/test-role": mock_aiosession
        }

        sessions = []
        async for account_info, session in strategy.get_account_sessions():
            sessions.append((account_info, session))

        assert len(sessions) == 1
        account_info, session = sessions[0]
        assert account_info["Id"] == "123456789012"
        assert account_info["Name"] == "Account 123456789012"
        assert session == mock_aiosession


class TestMultiAccountHealthCheckMixin:
    """Test MultiAccountHealthCheckMixin."""

    @pytest.fixture
    def strategy(
        self, mock_multi_account_config: dict[str, object]
    ) -> MultiAccountStrategy:
        """Create a MultiAccountStrategy instance."""
        provider = AssumeRoleProvider(config=mock_multi_account_config)
        return MultiAccountStrategy(provider=provider, config=mock_multi_account_config)

    def test_valid_arns_property(self, strategy: MultiAccountStrategy) -> None:
        """Test valid_arns property returns the list of valid ARNs."""
        strategy._valid_arns = ["arn1", "arn2"]
        assert strategy.valid_arns == ["arn1", "arn2"]

    def test_valid_arns_property_when_not_initialized(
        self, strategy: MultiAccountStrategy
    ) -> None:
        """Test valid_arns property returns empty list when _valid_arns doesn't exist."""
        # Ensure _valid_arns doesn't exist
        if hasattr(strategy, "_valid_arns"):
            delattr(strategy, "_valid_arns")
        assert strategy.valid_arns == []

    @pytest.mark.asyncio
    async def test_can_assume_role_success(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test _can_assume_role returns session when role can be assumed."""
        with patch.object(
            strategy.provider, "get_session", return_value=mock_aiosession
        ):
            result = await strategy._can_assume_role(
                "arn:aws:iam::123456789012:role/test-role"
            )
            assert result == mock_aiosession

    @pytest.mark.asyncio
    async def test_can_assume_role_failure(
        self, strategy: MultiAccountStrategy
    ) -> None:
        """Test _can_assume_role returns None when role cannot be assumed."""
        with patch.object(
            strategy.provider,
            "get_session",
            side_effect=Exception("Assume role failed"),
        ):
            result = await strategy._can_assume_role(
                "arn:aws:iam::123456789012:role/test-role"
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_healthcheck_success(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds with valid role ARNs."""
        with patch.object(strategy, "_can_assume_role", return_value=mock_aiosession):
            result = await strategy.healthcheck()
            assert result is True
            assert len(strategy._valid_arns) == 2
            assert len(strategy._valid_sessions) == 2

    @pytest.mark.asyncio
    async def test_healthcheck_no_arns(self, strategy: MultiAccountStrategy) -> None:
        """Test healthcheck fails when no role ARNs provided."""
        strategy.config = {"region": "us-west-2"}  # No account_role_arn
        result = await strategy.healthcheck()
        assert result is False

    @pytest.mark.asyncio
    async def test_healthcheck_empty_arns(self, strategy: MultiAccountStrategy) -> None:
        """Test healthcheck fails when empty role ARNs list provided."""
        strategy.config = {"account_role_arn": [], "region": "us-west-2"}
        result = await strategy.healthcheck()
        assert result is False

    @pytest.mark.asyncio
    async def test_healthcheck_partial_failure(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds when some roles can be assumed."""
        with patch.object(strategy, "_can_assume_role") as mock_can_assume:
            # First role succeeds, second fails
            mock_can_assume.side_effect = [mock_aiosession, None]
            result = await strategy.healthcheck()
            assert result is True
            assert len(strategy._valid_arns) == 1
            assert len(strategy._valid_sessions) == 1

    @pytest.mark.asyncio
    async def test_healthcheck_all_failures(
        self, strategy: MultiAccountStrategy
    ) -> None:
        """Test healthcheck raises error when no roles can be assumed."""
        with patch.object(strategy, "_can_assume_role", return_value=None):
            with pytest.raises(
                AWSSessionError, match="No accounts are accessible after health check"
            ):
                await strategy.healthcheck()

    @pytest.mark.asyncio
    async def test_healthcheck_concurrency_control(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck respects concurrency limits."""
        with patch.object(strategy, "_can_assume_role", return_value=mock_aiosession):
            with patch("asyncio.Semaphore") as mock_semaphore:
                mock_semaphore_instance = AsyncMock()
                mock_semaphore.return_value = mock_semaphore_instance
                result = await strategy.healthcheck()
                assert result is True
                mock_semaphore.assert_called_with(strategy.DEFAULT_CONCURRENCY)

    @pytest.mark.asyncio
    async def test_healthcheck_batching(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck processes ARNs in batches."""
        # Add more ARNs to test batching
        strategy.config["account_role_arn"] = [
            f"arn:aws:iam::{i:012d}:role/test-role" for i in range(25)
        ]
        with patch.object(strategy, "_can_assume_role", return_value=mock_aiosession):
            result = await strategy.healthcheck()
            assert result is True
            assert len(strategy._valid_arns) == 25
            assert len(strategy._valid_sessions) == 25
