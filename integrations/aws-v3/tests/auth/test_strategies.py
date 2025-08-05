import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.organizations_strategy import (
    OrganizationsStrategy,
)
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.utils import AWSSessionError
from typing import Any, AsyncIterator


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


class TestOrganizationsHealthCheckMixin:
    """Test OrganizationsHealthCheckMixin."""

    @pytest.fixture
    def mock_organizations_config(self) -> dict[str, object]:
        """Create a mock organizations configuration."""
        return {
            "account_role_arn": [
                "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole"
            ]
        }

    @pytest.fixture
    def strategy(
        self, mock_organizations_config: dict[str, object]
    ) -> OrganizationsStrategy:
        """Create an OrganizationsStrategy instance for testing the mixin."""
        provider = StaticCredentialProvider(config=mock_organizations_config)
        return OrganizationsStrategy(
            provider=provider, config=mock_organizations_config
        )

    def test_initialization(self, strategy: OrganizationsStrategy) -> None:
        """Test OrganizationsHealthCheckMixin initialization."""
        assert strategy._organization_role_name is None
        assert strategy._valid_arns == []
        assert strategy._valid_sessions == {}
        assert strategy._organization_session is None
        assert strategy._discovered_accounts == []

    def test_get_organization_account_role_arn(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _get_organization_account_role_arn returns correct ARN."""
        arn = strategy._get_organization_account_role_arn()
        assert arn == "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole"

    def test_get_organization_account_role_arn_missing(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _get_organization_account_role_arn raises error when missing."""
        strategy.config["account_role_arn"] = None
        with pytest.raises(AWSSessionError, match="account_role_arn is required"):
            strategy._get_organization_account_role_arn()

    def test_get_organization_account_role_arn_empty_list(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _get_organization_account_role_arn raises error when empty list."""
        strategy.config["account_role_arn"] = []
        with pytest.raises(AWSSessionError, match="account_role_arn is required"):
            strategy._get_organization_account_role_arn()

    def test_get_organization_account_role_name(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _get_organization_account_role_name extracts role name correctly."""
        role_name = strategy._get_organization_account_role_name()
        assert role_name == "OrganizationAccountAccessRole"

    def test_get_organization_account_role_name_invalid_arn(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _get_organization_account_role_name raises error for invalid ARN."""
        strategy.config["account_role_arn"] = ["invalid-arn"]
        with pytest.raises(
            AWSSessionError, match="account_role_arn must be a valid ARN"
        ):
            strategy._get_organization_account_role_name()

    @pytest.mark.asyncio
    async def test_get_organization_session_success(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test _get_organization_session creates session successfully."""
        with patch.object(
            strategy.provider, "get_session", return_value=mock_aiosession
        ):
            session = await strategy._get_organization_session()

            assert session == mock_aiosession
            assert strategy._organization_session == mock_aiosession

    @pytest.mark.asyncio
    async def test_get_organization_session_failure(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _get_organization_session raises error on failure."""
        with patch.object(
            strategy.provider,
            "get_session",
            side_effect=Exception("Role assumption failed"),
        ):
            with pytest.raises(
                AWSSessionError, match="Cannot assume organization role"
            ):
                await strategy._get_organization_session()

    @pytest.mark.asyncio
    async def test_discover_accounts_success(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test _discover_accounts discovers accounts successfully."""
        mock_org_client = AsyncMock()
        mock_paginator = AsyncMock()

        # Create an async iterator for the paginate method
        async def mock_paginate() -> AsyncIterator[dict[str, Any]]:
            yield {
                "Accounts": [
                    {
                        "Id": "123456789012",
                        "Name": "Test Account 1",
                        "Status": "ACTIVE",
                        "Email": "test1@example.com",
                        "Arn": "arn:aws:organizations::123456789012:account/o-1234567890/123456789012",
                    },
                    {
                        "Id": "123456789013",
                        "Name": "Test Account 2",
                        "Status": "ACTIVE",
                        "Email": "test2@example.com",
                        "Arn": "arn:aws:organizations::123456789012:account/o-1234567890/123456789013",
                    },
                    {
                        "Id": "123456789014",
                        "Name": "Suspended Account",
                        "Status": "SUSPENDED",
                        "Email": "suspended@example.com",
                        "Arn": "arn:aws:organizations::123456789012:account/o-1234567890/123456789014",
                    },
                ]
            }

        mock_paginator.paginate = mock_paginate
        mock_org_client.get_paginator = MagicMock(return_value=mock_paginator)

        with patch.object(mock_aiosession, "create_client") as mock_create_client:
            mock_create_client.return_value.__aenter__.return_value = mock_org_client
            with patch.object(
                strategy, "_get_organization_session", return_value=mock_aiosession
            ):
                accounts = await strategy._discover_accounts()

                assert len(accounts) == 2  # Only active accounts
                assert accounts[0]["Id"] == "123456789012"
                assert accounts[0]["Name"] == "Test Account 1"
                assert accounts[0]["Email"] == "test1@example.com"
                assert (
                    accounts[0]["Arn"]
                    == "arn:aws:organizations::123456789012:account/o-1234567890/123456789012"
                )
                assert accounts[1]["Id"] == "123456789013"
                assert accounts[1]["Name"] == "Test Account 2"
                assert accounts[1]["Email"] == "test2@example.com"
                assert (
                    accounts[1]["Arn"]
                    == "arn:aws:organizations::123456789012:account/o-1234567890/123456789013"
                )

    @pytest.mark.asyncio
    async def test_discover_accounts_access_denied(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test _discover_accounts handles access denied error."""
        mock_org_client = AsyncMock()
        mock_org_client.get_paginator.side_effect = Exception("AccessDeniedException")

        with patch.object(mock_aiosession, "create_client") as mock_create_client:
            mock_create_client.return_value.__aenter__.return_value = mock_org_client
            with patch.object(
                strategy, "_get_organization_session", return_value=mock_aiosession
            ):
                with pytest.raises(
                    AWSSessionError, match="Failed to discover accounts"
                ):
                    await strategy._discover_accounts()

    @pytest.mark.asyncio
    async def test_can_assume_role_in_account_success(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test _can_assume_role_in_account succeeds."""
        with patch.object(
            strategy.provider, "get_session", return_value=mock_aiosession
        ):
            session = await strategy._can_assume_role_in_account("123456789012")
            assert session == mock_aiosession

    @pytest.mark.asyncio
    async def test_can_assume_role_in_account_failure(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test _can_assume_role_in_account returns None on failure."""
        with patch.object(
            strategy.provider,
            "get_session",
            side_effect=Exception("Role assumption failed"),
        ):
            session = await strategy._can_assume_role_in_account("123456789012")
            assert session is None

    @pytest.mark.asyncio
    async def test_healthcheck_success(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds with valid accounts."""
        mock_accounts = [
            {"Id": "123456789012", "Name": "Test Account 1", "Status": "ACTIVE"},
            {"Id": "123456789013", "Name": "Test Account 2", "Status": "ACTIVE"},
        ]

        with patch.object(strategy, "_discover_accounts", return_value=mock_accounts):
            with patch.object(
                strategy, "_can_assume_role_in_account", return_value=mock_aiosession
            ):
                result = await strategy.healthcheck()
                assert result is True
                assert (
                    len(strategy._valid_arns) == 2
                )  # Only account ARNs are added during health check
                assert len(strategy._valid_sessions) == 2
                # Verify the account ARNs are correctly formatted
                expected_arns = [
                    "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole",
                    "arn:aws:iam::123456789013:role/OrganizationAccountAccessRole",
                ]
                assert strategy._valid_arns == expected_arns

    @pytest.mark.asyncio
    async def test_healthcheck_no_accounts(
        self, strategy: OrganizationsStrategy
    ) -> None:
        """Test healthcheck fails when no accounts discovered."""
        with patch.object(strategy, "_discover_accounts", return_value=[]):
            result = await strategy.healthcheck()
            assert result is False

    @pytest.mark.asyncio
    async def test_healthcheck_partial_failure(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test healthcheck succeeds with partial role assumption failures."""
        mock_accounts = [
            {"Id": "123456789012", "Name": "Test Account 1", "Status": "ACTIVE"},
            {"Id": "123456789013", "Name": "Test Account 2", "Status": "ACTIVE"},
        ]

        with patch.object(strategy, "_discover_accounts", return_value=mock_accounts):
            with patch.object(
                strategy,
                "_can_assume_role_in_account",
                side_effect=[mock_aiosession, None],
            ):
                result = await strategy.healthcheck()
                assert result is True
                assert (
                    len(strategy._valid_arns) == 1
                )  # Only successful account ARN is added
                assert len(strategy._valid_sessions) == 1
                # Verify the account ARN is correctly formatted
                expected_arn = (
                    "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole"
                )
                assert strategy._valid_arns == [expected_arn]


class TestOrganizationsStrategy:
    """Test OrganizationsStrategy."""

    @pytest.fixture
    def mock_organizations_config(self) -> dict[str, object]:
        """Create a mock organizations configuration."""
        return {
            "account_role_arn": [
                "arn:aws:iam::123456789012:role/OrganizationAccountAccessRole"
            ]
        }

    @pytest.fixture
    def strategy(
        self, mock_organizations_config: dict[str, object]
    ) -> OrganizationsStrategy:
        """Create an OrganizationsStrategy instance."""
        provider = StaticCredentialProvider(config=mock_organizations_config)
        return OrganizationsStrategy(
            provider=provider, config=mock_organizations_config
        )

    @pytest.mark.asyncio
    async def test_get_account_sessions(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_account_sessions yields account info and sessions."""
        mock_accounts = [
            {"Id": "123456789012", "Name": "Test Account 1", "Status": "ACTIVE"},
            {"Id": "123456789013", "Name": "Test Account 2", "Status": "ACTIVE"},
        ]

        with patch.object(strategy, "_discover_accounts", return_value=mock_accounts):
            with patch.object(
                strategy, "_can_assume_role_in_account", return_value=mock_aiosession
            ):
                sessions = []
                async for account_info, session in strategy.get_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 2
                assert sessions[0][0]["Id"] == "123456789012"
                assert sessions[0][1] == mock_aiosession
                assert sessions[1][0]["Id"] == "123456789013"
                assert sessions[1][1] == mock_aiosession

    @pytest.mark.asyncio
    async def test_get_account_sessions_with_failed_accounts(
        self, strategy: OrganizationsStrategy, mock_aiosession: AsyncMock
    ) -> None:
        """Test get_account_sessions skips accounts where role assumption fails."""
        mock_accounts = [
            {"Id": "123456789012", "Name": "Test Account 1", "Status": "ACTIVE"},
            {"Id": "123456789013", "Name": "Test Account 2", "Status": "ACTIVE"},
        ]

        with patch.object(strategy, "_discover_accounts", return_value=mock_accounts):
            with patch.object(
                strategy,
                "_can_assume_role_in_account",
                side_effect=[mock_aiosession, None],
            ):
                sessions = []
                async for account_info, session in strategy.get_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 1
                assert sessions[0][0]["Id"] == "123456789012"
                assert sessions[0][1] == mock_aiosession
