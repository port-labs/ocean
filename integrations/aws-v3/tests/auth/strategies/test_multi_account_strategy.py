import pytest
from unittest.mock import patch, AsyncMock

from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.utils import AWSSessionError
from tests.conftest import AWS_TEST_ROLE_ARN_2


class TestMultiAccountStrategy:
    """Test MultiAccountStrategy behavior."""

    def test_initialization(self, role_arn: str) -> None:
        """Test strategy initialization."""
        # Arrange & Act
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        # Assert
        assert strategy.provider == provider
        assert strategy.config == {"account_role_arn": [role_arn]}
        assert strategy.valid_arns == []

    @pytest.mark.asyncio
    async def test_successful_role_assumption_through_healthcheck(
        self, role_arn: str
    ) -> None:
        """Test successful role assumption behavior through public healthcheck method."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        mock_session = AsyncMock()

        with patch.object(provider, "get_session", return_value=mock_session):
            # Act
            result = await strategy.healthcheck()

            # Assert - Test behavior through public interface
            assert result is True
            assert role_arn in strategy.valid_arns

    @pytest.mark.asyncio
    async def test_failed_role_assumption_through_healthcheck(
        self, role_arn: str
    ) -> None:
        """Test failed role assumption behavior through public healthcheck method."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        with patch.object(
            provider, "get_session", side_effect=Exception("Role assumption failed")
        ):
            # Act & Assert - Test behavior through public interface
            with pytest.raises(
                AWSSessionError, match="No accounts are accessible after health check"
            ):
                await strategy.healthcheck()

            # Verify no valid ARNs were cached
            assert strategy.valid_arns == []

    @pytest.mark.asyncio
    async def test_healthcheck_caches_successful_sessions(self, role_arn: str) -> None:
        """Test that healthcheck caches successful sessions."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        mock_session = AsyncMock()

        with patch.object(provider, "get_session", return_value=mock_session):
            # Act
            result = await strategy.healthcheck()

            # Assert
            assert result is True
            assert role_arn in strategy.valid_arns  # Use public property

            # Verify the session is actually available by testing behavior
            sessions = []
            async for account_info, session in strategy.get_account_sessions():
                sessions.append((account_info, session))

            assert len(sessions) == 1
            assert sessions[0][1] == mock_session

    @pytest.mark.asyncio
    async def test_healthcheck_does_not_cache_failed_sessions(
        self, role_arn: str
    ) -> None:
        """Test that healthcheck does not cache failed sessions."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        with patch.object(
            provider, "get_session", side_effect=Exception("Role assumption failed")
        ):
            # Act & Assert
            with pytest.raises(
                AWSSessionError, match="No accounts are accessible after health check"
            ):
                await strategy.healthcheck()

            # Use public property to verify no valid ARNs
            assert role_arn not in strategy.valid_arns
            assert strategy.valid_arns == []

    @pytest.mark.asyncio
    async def test_get_account_sessions_single_role(self, role_arn: str) -> None:
        """Test get_account_sessions with single role ARN."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        mock_session = AsyncMock()

        with patch.object(provider, "get_session", return_value=mock_session):
            # Act - Let healthcheck populate internal state properly
            await strategy.healthcheck()

            sessions = []
            async for account_info, session in strategy.get_account_sessions():
                sessions.append((account_info, session))

            # Assert
            assert len(sessions) == 1
            account_info, session = sessions[0]
            assert "Id" in account_info
            assert "Name" in account_info
            assert session == mock_session

    @pytest.mark.asyncio
    async def test_get_account_sessions_multiple_roles(self, role_arn: str) -> None:
        """Test get_account_sessions with multiple role ARNs."""
        # Arrange
        provider = AssumeRoleProvider()
        role_arns = [role_arn, AWS_TEST_ROLE_ARN_2]
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": role_arns}
        )

        mock_session = AsyncMock()

        with patch.object(provider, "get_session", return_value=mock_session):
            # Act - Let healthcheck populate internal state properly
            await strategy.healthcheck()

            sessions = []
            async for account_info, session in strategy.get_account_sessions():
                sessions.append((account_info, session))

            # Assert
            assert len(sessions) == 2
            assert sessions[0][1] == mock_session
            assert sessions[1][1] == mock_session

    @pytest.mark.asyncio
    async def test_get_account_sessions_all_failures(self, role_arn: str) -> None:
        """Test get_account_sessions when all role assumptions fail."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [role_arn]}
        )

        with patch.object(
            provider, "get_session", side_effect=Exception("Role assumption failed")
        ):
            with patch.object(
                strategy,
                "healthcheck",
                side_effect=AWSSessionError(
                    "No accounts are accessible after health check"
                ),
            ):
                # Act & Assert
                with pytest.raises(
                    AWSSessionError,
                    match="No accounts are accessible after health check",
                ):
                    async for account_info, session in strategy.get_account_sessions():
                        pass

    @pytest.mark.asyncio
    async def test_get_account_sessions_empty_role_list(self) -> None:
        """Test get_account_sessions with empty role ARN list."""
        # Arrange
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": []}
        )

        with patch.object(
            strategy,
            "healthcheck",
            side_effect=AWSSessionError(
                "Account sessions not initialized. Run healthcheck first."
            ),
        ):
            # Act & Assert
            with pytest.raises(
                AWSSessionError,
                match="Account sessions not initialized. Run healthcheck first.",
            ):
                async for account_info, session in strategy.get_account_sessions():
                    pass
