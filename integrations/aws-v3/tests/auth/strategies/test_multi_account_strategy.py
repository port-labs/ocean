import pytest
from typing import Any
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.utils import AWSSessionError
from unittest.mock import patch, AsyncMock

from tests.conftest import AWS_TEST_ACCOUNT_ID, AWS_TEST_ROLE_ARN


class TestMultiAccountStrategy:
    """Test MultiAccountStrategy behavior."""

    def test_initialization(self) -> None:
        """Test strategy initializes with provider and config."""
        provider = AssumeRoleProvider()
        config = {"account_role_arn": [AWS_TEST_ROLE_ARN]}
        strategy = MultiAccountStrategy(provider=provider, config=config)

        assert strategy.provider == provider
        assert strategy.config == config
        assert strategy._valid_sessions == {}

    @pytest.mark.asyncio
    async def test_can_assume_role_success(self, mock_session_with_sts: Any) -> None:
        """Test successful role assumption."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            result = await strategy._can_assume_role(AWS_TEST_ROLE_ARN)

            assert result == mock_session_with_sts

    @pytest.mark.asyncio
    async def test_can_assume_role_failure(self) -> None:
        """Test failed role assumption."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Role assumption failed")

            result = await strategy._can_assume_role(AWS_TEST_ROLE_ARN)

            assert result is None

    @pytest.mark.asyncio
    async def test_can_assume_role_caches_successful_sessions(
        self, mock_session_with_sts: Any
    ) -> None:
        """Test that successful sessions are cached."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            result1 = await strategy._can_assume_role(AWS_TEST_ROLE_ARN)
            assert result1 == mock_session_with_sts
            assert mock_get_session.call_count == 1

            result2 = await strategy._can_assume_role(AWS_TEST_ROLE_ARN)
            assert result2 == mock_session_with_sts
            assert mock_get_session.call_count == 2

    @pytest.mark.asyncio
    async def test_can_assume_role_caches_failed_sessions(self) -> None:
        """Test that failed sessions are cached."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Role assumption failed")

            result1 = await strategy._can_assume_role(AWS_TEST_ROLE_ARN)
            assert result1 is None
            assert mock_get_session.call_count == 1

            result2 = await strategy._can_assume_role(AWS_TEST_ROLE_ARN)
            assert result2 is None
            assert mock_get_session.call_count == 2

    @pytest.mark.asyncio
    async def test_get_account_sessions_single_role(
        self, mock_session_with_sts: Any
    ) -> None:
        """Test get_account_sessions with single role ARN."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            with patch.object(strategy, "healthcheck") as mock_healthcheck:
                mock_healthcheck.return_value = True
                strategy._valid_arns = [AWS_TEST_ROLE_ARN]
                strategy._valid_sessions = {AWS_TEST_ROLE_ARN: mock_session_with_sts}

                sessions = []
                async for account_info, session in strategy.get_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 1
                account_info, session = sessions[0]
                assert account_info["Id"] == AWS_TEST_ACCOUNT_ID
                assert account_info["Name"] == f"Account {AWS_TEST_ACCOUNT_ID}"
                assert session == mock_session_with_sts

    @pytest.mark.asyncio
    async def test_get_account_sessions_multiple_roles(
        self, mock_session_with_sts: Any
    ) -> None:
        """Test get_account_sessions with multiple role ARNs."""
        provider = AssumeRoleProvider()
        role_arns = [
            AWS_TEST_ROLE_ARN,
            "arn:aws:iam::987654321098:role/test-role-2",
        ]
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": role_arns}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            with patch.object(strategy, "healthcheck") as mock_healthcheck:
                mock_healthcheck.return_value = True
                strategy._valid_arns = role_arns
                strategy._valid_sessions = {
                    arn: mock_session_with_sts for arn in role_arns
                }

                sessions = []
                async for account_info, session in strategy.get_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 2
                assert sessions[0][0]["Id"] == AWS_TEST_ACCOUNT_ID
                assert sessions[0][0]["Name"] == f"Account {AWS_TEST_ACCOUNT_ID}"
                assert sessions[0][1] == mock_session_with_sts
                assert sessions[1][0]["Id"] == "987654321098"
                assert sessions[1][0]["Name"] == "Account 987654321098"
                assert sessions[1][1] == mock_session_with_sts

    @pytest.mark.asyncio
    async def test_get_account_sessions_mixed_success_failure(
        self, mock_session_with_sts: Any
    ) -> None:
        """Test get_account_sessions with mix of successful and failed role assumptions."""
        provider = AssumeRoleProvider()
        role_arns = [
            AWS_TEST_ROLE_ARN,  # This one will succeed
            "arn:aws:iam::987654321098:role/test-role-2",  # This one will fail
        ]
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": role_arns}
        )

        with patch.object(provider, "get_session") as mock_get_session:

            def mock_get_session_side_effect(role_arn: str, **kwargs: Any) -> AsyncMock:
                if role_arn == AWS_TEST_ROLE_ARN:
                    return mock_session_with_sts
                else:
                    raise Exception("Role assumption failed")

            mock_get_session.side_effect = mock_get_session_side_effect

            with patch.object(strategy, "healthcheck") as mock_healthcheck:
                mock_healthcheck.return_value = True
                strategy._valid_arns = [AWS_TEST_ROLE_ARN]
                strategy._valid_sessions = {AWS_TEST_ROLE_ARN: mock_session_with_sts}

                sessions = []
                async for account_info, session in strategy.get_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 1
                account_info, session = sessions[0]
                assert account_info["Id"] == AWS_TEST_ACCOUNT_ID
                assert account_info["Name"] == f"Account {AWS_TEST_ACCOUNT_ID}"
                assert session == mock_session_with_sts

    @pytest.mark.asyncio
    async def test_get_account_sessions_all_failures(self) -> None:
        """Test get_account_sessions when all role assumptions fail."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Role assumption failed")

            with patch.object(strategy, "healthcheck") as mock_healthcheck:
                mock_healthcheck.side_effect = AWSSessionError(
                    "No accounts are accessible after health check"
                )

                with pytest.raises(
                    AWSSessionError,
                    match="No accounts are accessible after health check",
                ):
                    async for account_info, session in strategy.get_account_sessions():
                        pass

    @pytest.mark.asyncio
    async def test_get_account_sessions_empty_role_list(self) -> None:
        """Test get_account_sessions with empty role ARN list."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": []}
        )

        with patch.object(strategy, "healthcheck") as mock_healthcheck:
            mock_healthcheck.side_effect = AWSSessionError(
                "Account sessions not initialized. Run healthcheck first."
            )

            with pytest.raises(
                AWSSessionError,
                match="Account sessions not initialized. Run healthcheck first.",
            ):
                async for account_info, session in strategy.get_account_sessions():
                    pass

    @pytest.mark.asyncio
    async def test_get_account_sessions_string_role_arn(
        self, mock_session_with_sts: Any
    ) -> None:
        """Test get_account_sessions with string role ARN instead of list."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": AWS_TEST_ROLE_ARN}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.return_value = mock_session_with_sts

            with patch.object(strategy, "healthcheck") as mock_healthcheck:
                mock_healthcheck.return_value = True
                strategy._valid_arns = [AWS_TEST_ROLE_ARN]
                strategy._valid_sessions = {AWS_TEST_ROLE_ARN: mock_session_with_sts}

                sessions = []
                async for account_info, session in strategy.get_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 1
                account_info, session = sessions[0]
                assert account_info["Id"] == AWS_TEST_ACCOUNT_ID
                assert account_info["Name"] == f"Account {AWS_TEST_ACCOUNT_ID}"
                assert session == mock_session_with_sts

    @pytest.mark.asyncio
    async def test_get_account_sessions_handles_session_creation_error(self) -> None:
        """Test get_account_sessions handles session creation errors gracefully."""
        provider = AssumeRoleProvider()
        strategy = MultiAccountStrategy(
            provider=provider, config={"account_role_arn": [AWS_TEST_ROLE_ARN]}
        )

        with patch.object(provider, "get_session") as mock_get_session:
            mock_get_session.side_effect = Exception("Session creation failed")

            with patch.object(strategy, "healthcheck") as mock_healthcheck:
                mock_healthcheck.side_effect = AWSSessionError(
                    "No accounts are accessible after health check"
                )

                with pytest.raises(
                    AWSSessionError,
                    match="No accounts are accessible after health check",
                ):
                    async for account_info, session in strategy.get_account_sessions():
                        pass
