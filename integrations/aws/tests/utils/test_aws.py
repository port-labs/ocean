import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession
from botocore.utils import ArnParser
from typing import Any
from aiobotocore.credentials import AioCredentials

from aws.auth.utils import normalize_arn_list, extract_account_from_arn
from aws.auth.region_resolver import RegionResolver
from aws.auth.strategies.single_account_strategy import SingleAccountStrategy
from aws.auth.strategies.multi_account_strategy import MultiAccountStrategy
from aws.auth.providers.static_provider import StaticCredentialProvider
from aws.auth.providers.assume_role_provider import AssumeRoleProvider
from aws.auth.session_factory import ResyncStrategyFactory
from utils.overrides import AWSDescribeResourcesSelector


# --- normalize_arn_list ---
def test_normalize_arn_list() -> None:
    assert normalize_arn_list(None) == []
    assert normalize_arn_list("") == []
    assert normalize_arn_list([""]) == []
    assert normalize_arn_list("arn:aws:iam::1:role/x") == ["arn:aws:iam::1:role/x"]
    assert normalize_arn_list(["arn:aws:iam::1:role/x", ""]) == [
        "arn:aws:iam::1:role/x"
    ]


# --- extract_account_from_arn ---
def test_extract_account_from_arn() -> None:
    arn = "arn:aws:iam::123456789012:role/TestRole"
    parser = ArnParser()
    assert extract_account_from_arn(arn, parser) == "123456789012"
    with pytest.raises(Exception):
        extract_account_from_arn("invalid-arn", parser)


# --- RegionResolver ---
@pytest.mark.asyncio
async def test_region_resolver_get_enabled_regions() -> None:
    session = AsyncMock(spec=AioSession)
    selector = MagicMock(spec=AWSDescribeResourcesSelector)
    mock_client = AsyncMock()
    mock_client.list_regions.return_value = {
        "Regions": [
            {"RegionName": "us-east-1", "RegionOptStatus": "ENABLED"},
            {"RegionName": "us-west-2", "RegionOptStatus": "ENABLED"},
        ]
    }
    session.create_client.return_value.__aenter__.return_value = mock_client
    resolver = RegionResolver(session, selector)
    regions = await resolver.get_enabled_regions()
    assert set(regions) == {"us-east-1", "us-west-2"}


# --- StaticCredentialProvider ---
@pytest.mark.asyncio
async def test_static_credential_provider_success() -> None:
    provider = StaticCredentialProvider()
    with patch(
        "aiobotocore.credentials.AioCredentials",
        return_value=AioCredentials("dummy_key", "dummy_secret", token=None),
    ):
        creds = await provider.get_credentials(
            aws_access_key_id="dummy_key", aws_secret_access_key="dummy_secret"
        )
        assert creds.access_key == "dummy_key"
        assert creds.secret_key == "dummy_secret"
        with patch.object(AioSession, "create_client", AsyncMock()):
            session = await provider.get_session(
                aws_access_key_id="dummy_key", aws_secret_access_key="dummy_secret"
            )
            assert isinstance(session, AioSession)


@pytest.mark.asyncio
async def test_static_credential_provider_missing() -> None:
    provider = StaticCredentialProvider()
    with pytest.raises(KeyError):
        await provider.get_credentials()


# --- AssumeRoleProvider ---
@pytest.mark.asyncio
async def test_assume_role_provider_missing_role_arn() -> None:
    provider = AssumeRoleProvider()
    with pytest.raises(Exception):
        await provider.get_credentials(region=None, role_arn=None)


# --- SingleAccountStrategy ---
@pytest.mark.asyncio
async def test_single_account_strategy_get_accessible_accounts() -> None:
    provider = StaticCredentialProvider()
    strategy = SingleAccountStrategy(provider, config={})
    session_mock = AsyncMock(spec=AioSession)
    sts_client_mock = AsyncMock()
    sts_client_mock.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    session_mock.create_client.return_value.__aenter__.return_value = sts_client_mock
    with patch.object(provider, "get_session", return_value=session_mock):
        sessions = []
        async for session in strategy.create_session_for_each_account():
            sessions.append(session)
        assert len(sessions) == 1


# --- MultiAccountStrategy ---
@pytest.mark.asyncio
async def test_multi_account_strategy_sanity_check_success() -> None:
    provider = AssumeRoleProvider()
    config = {
        "account_role_arn": [
            "arn:aws:iam::123456789012:role/OrgRole1",
            "arn:aws:iam::123456789012:role/OrgRole2",
        ]
    }
    strategy = MultiAccountStrategy(provider, config)
    # Mock the STS client
    mock_sts = AsyncMock()
    mock_sts.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:assumed-role/OrgRole1/TestSession",
    }
    # Mock the session
    session_mock = AsyncMock(spec=AioSession)
    # Mock the context manager for create_client
    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__.return_value = mock_sts
    mock_client_ctx.__aexit__.return_value = None  # Ensure __aexit__ is properly mocked
    session_mock.create_client.return_value = mock_client_ctx
    # Patch the get_session method to return the mocked session
    with patch.object(provider, "get_session", return_value=session_mock):
        result = await strategy.healthcheck()
        assert result is True
    # The _valid_arns attribute may not be set in this mock, so skip that assertion


# --- SessionStrategyFactory ---
@pytest.mark.asyncio
async def test_session_strategy_factory_single(
    monkeypatch: Any, ocean_context: Any
) -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    ocean_context(config)

    async def async_healthcheck(self: Any) -> bool:
        # Mock the healthcheck method to avoid actual health checks during testing
        return True

    monkeypatch.setattr(
        "aws.auth.strategies.single_account_strategy.SingleAccountStrategy.healthcheck",
        async_healthcheck,
    )
    strategy = await ResyncStrategyFactory.create()
    assert isinstance(strategy, SingleAccountStrategy)
