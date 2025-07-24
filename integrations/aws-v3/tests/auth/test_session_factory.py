import pytest
from unittest.mock import patch, AsyncMock
from typing import Any, Dict, AsyncGenerator

from aws.auth.session_factory import ResyncStrategyFactory, get_all_account_sessions
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.web_identity_provider import WebIdentityCredentialProvider

from tests.conftest import AWS_TEST_ACCOUNT_ID


class TestResyncStrategyFactory:
    """Test ResyncStrategyFactory strategy selection logic."""

    @pytest.mark.asyncio
    async def test_creates_single_account_strategy_by_default(
        self, aws_credentials: Any
    ) -> None:
        """Test factory creates SingleAccountStrategy when no account_role_arn provided."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = aws_credentials

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, SingleAccountStrategy)
            assert isinstance(strategy.provider, StaticCredentialProvider)

    @pytest.mark.asyncio
    async def test_creates_multi_account_strategy_with_account_role_arn(
        self, multi_account_config: Any
    ) -> None:
        """Test factory creates MultiAccountStrategy when account_role_arn provided."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = multi_account_config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)

    @pytest.mark.asyncio
    async def test_creates_multi_account_strategy_with_oidc(
        self, oidc_config: Any
    ) -> None:
        """Test factory creates MultiAccountStrategy when oidc_token provided."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = oidc_config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, WebIdentityCredentialProvider)

    @pytest.mark.asyncio
    async def test_caches_strategy_between_calls(self, aws_credentials: Any) -> None:
        """Test factory caches strategy instance between calls."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = aws_credentials

            strategy1 = await ResyncStrategyFactory.create()
            strategy2 = await ResyncStrategyFactory.create()

            assert strategy1 is strategy2

    @pytest.mark.asyncio
    async def test_handles_empty_config(self) -> None:
        """Test factory handles empty configuration gracefully."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = {}

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, SingleAccountStrategy)
            assert isinstance(strategy.provider, StaticCredentialProvider)

    @pytest.mark.asyncio
    async def test_handles_none_config(self) -> None:
        """Test factory handles None configuration gracefully."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = None

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, SingleAccountStrategy)
            assert isinstance(strategy.provider, StaticCredentialProvider)

    @pytest.mark.asyncio
    async def test_creates_single_account_strategy_with_empty_account_role_arn_list(
        self,
    ) -> None:
        """Test factory creates SingleAccountStrategy when account_role_arn is empty list."""
        config: Dict[str, Any] = {"account_role_arn": []}

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, SingleAccountStrategy)
            assert isinstance(strategy.provider, StaticCredentialProvider)

    @pytest.mark.asyncio
    async def test_oidc_priority_over_multi_account(self, role_arn: str) -> None:
        """Test that OIDC takes priority over multi-account when both are present."""
        config_with_both = {
            "oidc_token": "test-oidc-token",
            "account_role_arn": [role_arn],
            "region": "us-west-2",
        }

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = config_with_both

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, WebIdentityCredentialProvider)

    @pytest.mark.asyncio
    async def test_oidc_priority_creates_web_identity_not_assume_role(
        self, role_arn: str
    ) -> None:
        """Test that OIDC priority creates WebIdentity provider instead of AssumeRole provider."""
        config_with_both = {
            "oidc_token": "test-oidc-token",
            "account_role_arn": [role_arn],
            "region": "us-west-2",
        }

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = config_with_both

            strategy = await ResyncStrategyFactory.create()

            assert not isinstance(strategy.provider, AssumeRoleProvider)
            assert isinstance(strategy.provider, WebIdentityCredentialProvider)

    @pytest.mark.asyncio
    async def test_get_all_account_sessions(self, aws_credentials: Any) -> None:
        """Test the main entry point function calls factory and yields data correctly."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = aws_credentials

            mock_strategy = AsyncMock()
            mock_session = AsyncMock()
            mock_account_info = {
                "Id": AWS_TEST_ACCOUNT_ID,
                "Name": f"Account {AWS_TEST_ACCOUNT_ID}",
            }

            async def mock_get_account_sessions() -> (
                AsyncGenerator[tuple[Dict[str, Any], Any], None]
            ):
                yield mock_account_info, mock_session

            mock_strategy.get_account_sessions = mock_get_account_sessions

            with patch.object(
                ResyncStrategyFactory, "create", return_value=mock_strategy
            ) as mock_create:
                sessions = []
                async for account_info, session in get_all_account_sessions():
                    sessions.append((account_info, session))

                mock_create.assert_called_once()

                assert len(sessions) == 1
                account_info, session = sessions[0]
                assert account_info["Id"] == AWS_TEST_ACCOUNT_ID
                assert account_info["Name"] == f"Account {AWS_TEST_ACCOUNT_ID}"
                assert session == mock_session

    @pytest.mark.asyncio
    async def test_get_all_account_sessions_converts_to_account_info(
        self, aws_credentials: Any
    ) -> None:
        """Test that get_all_account_sessions converts raw account info to AccountInfo TypedDict."""
        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = aws_credentials

            mock_strategy = AsyncMock()
            mock_session = AsyncMock()
            raw_account_info = {"Id": "987654321098", "Name": "Test Account"}

            async def mock_get_account_sessions() -> (
                AsyncGenerator[tuple[Dict[str, Any], Any], None]
            ):
                yield raw_account_info, mock_session

            mock_strategy.get_account_sessions = mock_get_account_sessions

            with patch.object(
                ResyncStrategyFactory, "create", return_value=mock_strategy
            ):
                sessions = []
                async for account_info, session in get_all_account_sessions():
                    sessions.append((account_info, session))

                assert len(sessions) == 1
                account_info, session = sessions[0]

                assert isinstance(account_info, dict)
                assert "Id" in account_info
                assert "Name" in account_info
                assert account_info["Id"] == "987654321098"
                assert account_info["Name"] == "Test Account"
                assert session == mock_session

    @pytest.mark.asyncio
    async def test_creates_multi_account_strategy_with_string_account_role_arn(
        self, role_arn: str
    ) -> None:
        """Test factory creates MultiAccountStrategy when account_role_arn is a string."""
        config = {"account_role_arn": role_arn}

        with patch("aws.auth.session_factory.ocean") as mock_ocean:
            mock_ocean.integration_config = config

            strategy = await ResyncStrategyFactory.create()

            assert isinstance(strategy, MultiAccountStrategy)
            assert isinstance(strategy.provider, AssumeRoleProvider)
