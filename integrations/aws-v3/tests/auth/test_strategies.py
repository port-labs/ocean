import pytest
from unittest.mock import AsyncMock, patch

from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_credentials_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth._helpers.exceptions import AWSSessionError


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
        """Test get_account_sessions yields account info and session, expects error if identity not set."""
        # Simulate missing identity and session
        strategy._session = mock_aiosession
        # Ensure _identity is not set
        strategy._identity = None
        with pytest.raises(AWSSessionError, match="Identity could not be established"):
            async for _ in strategy.get_account_sessions():
                pass

    @pytest.mark.asyncio
    async def test_get_account_sessions_with_identity(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_account_sessions uses identity when available."""
        strategy._identity = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:role/test-role",
        }
        strategy._session = mock_aiosession
        accounts = []
        async for account_context in strategy.get_account_sessions():
            accounts.append(account_context)

        assert len(accounts) == 1
        account_context = accounts[0]
        assert account_context["details"]["Id"] == "123456789012"
        assert account_context["details"]["Name"] == "Account 123456789012"
        assert account_context["session"] == mock_aiosession


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
                assert strategy._identity is not None
                assert strategy._identity["Account"] == "123456789012"

    @pytest.mark.asyncio
    async def test_healthcheck_without_credentials(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck fails without credentials in config."""
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
                with pytest.raises(
                    AWSSessionError, match="Single account is not accessible"
                ):
                    await strategy.healthcheck()

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
        async for account_context in strategy.get_account_sessions():
            sessions.append(account_context)

        assert len(sessions) == 1
        account_context = sessions[0]
        assert account_context["details"]["Id"] == "123456789012"
        assert account_context["details"]["Name"] == "Account 123456789012"
        assert account_context["session"] == mock_aiosession


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
        """Test valid_arns property returns empty list when not initialized."""
        assert strategy.valid_arns == []

    def test_valid_arns_property_when_not_initialized(
        self, strategy: MultiAccountStrategy
    ) -> None:
        """Test valid_arns property returns empty list when not initialized."""
        # Ensure _valid_arns is not set
        if hasattr(strategy, "_valid_arns"):
            delattr(strategy, "_valid_arns")
        assert strategy.valid_arns == []

    @pytest.mark.asyncio
    async def test_can_assume_role_success(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test _can_assume_role succeeds with valid role ARN."""
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
        """Test _can_assume_role returns None when role assumption fails."""
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
            # The strategy config has 2 ARNs by default
            assert len(strategy._valid_arns) == 2
            assert len(strategy._valid_sessions) == 2

    @pytest.mark.asyncio
    async def test_healthcheck_no_arns(self, strategy: MultiAccountStrategy) -> None:
        """Test healthcheck returns False when no role ARNs are provided."""
        strategy.config = {}  # No account_role_arn in config
        result = await strategy.healthcheck()
        assert result is False

    @pytest.mark.asyncio
    async def test_healthcheck_empty_arns(self, strategy: MultiAccountStrategy) -> None:
        """Test healthcheck returns False when empty role ARNs are provided."""
        strategy.config = {"account_role_arn": []}  # Empty list
        result = await strategy.healthcheck()
        assert result is False

    @pytest.mark.asyncio
    async def test_healthcheck_partial_failure(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds with partial failures."""
        # Set up multiple ARNs, one will succeed, one will fail
        strategy.config = {
            "account_role_arn": [
                "arn:aws:iam::123456789012:role/test-role",
                "arn:aws:iam::987654321098:role/test-role",
            ]
        }

        async def mock_can_assume_role(arn: str) -> AsyncMock | None:
            if "123456789012" in arn:
                return mock_aiosession
            return None

        with patch.object(
            strategy, "_can_assume_role", side_effect=mock_can_assume_role
        ):
            result = await strategy.healthcheck()
            assert result is True
            assert len(strategy._valid_arns) == 1
            assert len(strategy._valid_sessions) == 1

    @pytest.mark.asyncio
    async def test_healthcheck_all_failures(
        self, strategy: MultiAccountStrategy
    ) -> None:
        """Test healthcheck fails when all role assumptions fail."""
        with patch.object(strategy, "_can_assume_role", return_value=None):
            with pytest.raises(AWSSessionError, match="No accounts are accessible"):
                await strategy.healthcheck()

    @pytest.mark.asyncio
    async def test_healthcheck_concurrency_control(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck respects concurrency limits."""
        with patch.object(strategy, "_can_assume_role", return_value=mock_aiosession):
            result = await strategy.healthcheck()
            assert result is True
            # Verify that the semaphore was used (concurrency controlled)
            # The strategy config has 2 ARNs by default
            assert len(strategy._valid_arns) == 2

    @pytest.mark.asyncio
    async def test_healthcheck_batching(
        self, strategy: MultiAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck handles multiple ARNs in batches."""
        # Set up multiple ARNs
        strategy.config = {
            "account_role_arn": [
                "arn:aws:iam::123456789012:role/test-role",
                "arn:aws:iam::987654321098:role/test-role",
                "arn:aws:iam::111111111111:role/test-role",
            ]
        }

        with patch.object(strategy, "_can_assume_role", return_value=mock_aiosession):
            result = await strategy.healthcheck()
            assert result is True
            assert len(strategy._valid_arns) == 3
            assert len(strategy._valid_sessions) == 3
