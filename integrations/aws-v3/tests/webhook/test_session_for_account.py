"""Tests for `session_for_account(account_id)` across all three AWS strategies."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.strategies.organizations_strategy import OrganizationsStrategy
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy


class TestSingleAccountSessionForAccount:
    @pytest.fixture
    def strategy(
        self, mock_single_account_config: Dict[str, Any]
    ) -> SingleAccountStrategy:
        provider = StaticCredentialProvider(config=mock_single_account_config)
        return SingleAccountStrategy(
            provider=provider, config=mock_single_account_config
        )

    @pytest.mark.asyncio
    async def test_returns_session_for_matching_account(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        strategy.account_id = "123456789012"
        strategy._session = mock_aiosession

        result = await strategy.session_for_account("123456789012")

        assert result is mock_aiosession

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_account(
        self, strategy: SingleAccountStrategy, mock_aiosession: AsyncMock
    ) -> None:
        strategy.account_id = "123456789012"
        strategy._session = mock_aiosession

        result = await strategy.session_for_account("999999999999")

        assert result is None

    @pytest.mark.asyncio
    async def test_runs_healthcheck_when_session_missing(
        self,
        strategy: SingleAccountStrategy,
        mock_aiosession: AsyncMock,
    ) -> None:
        async def fake_healthcheck() -> bool:
            strategy.account_id = "123456789012"
            strategy._session = mock_aiosession
            return True

        with patch.object(
            strategy, "healthcheck", new=AsyncMock(side_effect=fake_healthcheck)
        ) as mock_healthcheck:
            result = await strategy.session_for_account("123456789012")

            assert result is mock_aiosession
            mock_healthcheck.assert_awaited_once()


class TestMultiAccountSessionForAccount:
    @pytest.fixture
    def strategy(
        self, mock_multi_account_config: Dict[str, Any]
    ) -> MultiAccountStrategy:
        provider = AssumeRoleProvider(config=mock_multi_account_config)
        return MultiAccountStrategy(provider=provider, config=mock_multi_account_config)

    @pytest.mark.asyncio
    async def test_returns_session_when_arn_matches(
        self, strategy: MultiAccountStrategy
    ) -> None:
        session_a = MagicMock(name="session_a")
        session_b = MagicMock(name="session_b")
        strategy._valid_arns = {
            "arn:aws:iam::123456789012:role/test-role-1",
            "arn:aws:iam::987654321098:role/test-role-2",
        }
        strategy._valid_sessions = {
            "arn:aws:iam::123456789012:role/test-role-1": session_a,
            "arn:aws:iam::987654321098:role/test-role-2": session_b,
        }

        result = await strategy.session_for_account("987654321098")

        assert result is session_b

    @pytest.mark.asyncio
    async def test_returns_none_when_no_arn_matches(
        self, strategy: MultiAccountStrategy
    ) -> None:
        session_a = MagicMock(name="session_a")
        strategy._valid_arns = {"arn:aws:iam::123456789012:role/test-role-1"}
        strategy._valid_sessions = {
            "arn:aws:iam::123456789012:role/test-role-1": session_a
        }

        result = await strategy.session_for_account("000000000000")

        assert result is None

    @pytest.mark.asyncio
    async def test_runs_healthcheck_when_state_empty(
        self, strategy: MultiAccountStrategy
    ) -> None:
        session = MagicMock(name="session")

        async def fake_healthcheck() -> bool:
            strategy._valid_arns = {"arn:aws:iam::123456789012:role/test-role-1"}
            strategy._valid_sessions = {
                "arn:aws:iam::123456789012:role/test-role-1": session
            }
            return True

        with patch.object(
            strategy, "healthcheck", new=AsyncMock(side_effect=fake_healthcheck)
        ) as mock_healthcheck:
            result = await strategy.session_for_account("123456789012")

            assert result is session
            mock_healthcheck.assert_awaited_once()


class TestOrganizationsSessionForAccount:
    @pytest.fixture
    def strategy(self) -> OrganizationsStrategy:
        config: Dict[str, Any] = {
            "account_role_arn": "arn:aws:iam::111111111111:role/OrgRole",
            "region": "us-west-2",
        }
        provider = AssumeRoleProvider(config=config)
        return OrganizationsStrategy(provider=provider, config=config)

    @pytest.mark.asyncio
    async def test_returns_session_when_account_validated(
        self, strategy: OrganizationsStrategy
    ) -> None:
        session = MagicMock(name="session")
        strategy._valid_arns = {"arn:aws:iam::222222222222:role/OrgRole"}
        strategy._valid_sessions = {"arn:aws:iam::222222222222:role/OrgRole": session}

        result = await strategy.session_for_account("222222222222")

        assert result is session

    @pytest.mark.asyncio
    async def test_returns_none_when_account_not_validated(
        self, strategy: OrganizationsStrategy
    ) -> None:
        session = MagicMock(name="session")
        strategy._valid_arns = {"arn:aws:iam::222222222222:role/OrgRole"}
        strategy._valid_sessions = {"arn:aws:iam::222222222222:role/OrgRole": session}

        result = await strategy.session_for_account("333333333333")

        assert result is None

    @pytest.mark.asyncio
    async def test_runs_healthcheck_when_state_empty(
        self, strategy: OrganizationsStrategy
    ) -> None:
        session = MagicMock(name="session")

        async def fake_healthcheck() -> bool:
            strategy._valid_arns = {"arn:aws:iam::222222222222:role/OrgRole"}
            strategy._valid_sessions = {
                "arn:aws:iam::222222222222:role/OrgRole": session
            }
            return True

        with patch.object(
            strategy, "healthcheck", new=AsyncMock(side_effect=fake_healthcheck)
        ) as mock_healthcheck:
            result = await strategy.session_for_account("222222222222")

            assert result is session
            mock_healthcheck.assert_awaited_once()
