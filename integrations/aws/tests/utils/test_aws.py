import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiobotocore.session import AioSession
from botocore.utils import ArnParser
from botocore.exceptions import ClientError

from aws.auth.account import (
    normalize_arn_list,
    extract_account_from_arn,
    RegionResolver,
    SingleAccountStrategy,
    MultiAccountStrategy,
)
from aws.auth.credentials_provider import (
    StaticCredentialProvider,
    AssumeRoleProvider,
    CredentialsProviderError,
)
from aws.auth.session_factory import SessionStrategyFactory
from utils.overrides import AWSDescribeResourcesSelector


# --- normalize_arn_list ---
def test_normalize_arn_list():
    assert normalize_arn_list(None) == []
    assert normalize_arn_list("") == []
    assert normalize_arn_list([""]) == []
    assert normalize_arn_list("arn:aws:iam::1:role/x") == ["arn:aws:iam::1:role/x"]
    assert normalize_arn_list(["arn:aws:iam::1:role/x", ""]) == [
        "arn:aws:iam::1:role/x"
    ]


# --- extract_account_from_arn ---
def test_extract_account_from_arn():
    arn = "arn:aws:iam::123456789012:role/TestRole"
    parser = ArnParser()
    assert extract_account_from_arn(arn, parser) == "123456789012"
    with pytest.raises(Exception):
        extract_account_from_arn("invalid-arn", parser)


# --- RegionResolver ---
@pytest.mark.asyncio
async def test_region_resolver_get_enabled_regions():
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
async def test_static_credential_provider_success():
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    provider = StaticCredentialProvider(config)
    creds = await provider.get_credentials(region=None)
    assert creds.access_key == "x"
    assert creds.secret_key == "y"
    session = await provider.get_session(region=None)
    assert isinstance(session, AioSession)


@pytest.mark.asyncio
async def test_static_credential_provider_missing():
    provider = StaticCredentialProvider({})
    with pytest.raises(CredentialsProviderError):
        await provider.get_credentials(region=None)


# --- AssumeRoleProvider ---
@pytest.mark.asyncio
async def test_assume_role_provider_missing_role_arn():
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    provider = AssumeRoleProvider(config)
    with pytest.raises(CredentialsProviderError):
        await provider.get_credentials(region=None, role_arn=None)


# --- SingleAccountStrategy ---
@pytest.mark.asyncio
async def test_single_account_strategy_get_accessible_accounts():
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    provider = StaticCredentialProvider(config)
    strategy = SingleAccountStrategy(provider)
    session_mock = AsyncMock(spec=AioSession)
    sts_client_mock = AsyncMock()
    sts_client_mock.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    session_mock.create_client.return_value.__aenter__.return_value = sts_client_mock
    with patch.object(provider, "get_session", return_value=session_mock):
        accounts = []
        async for account in strategy.get_accessible_accounts():
            accounts.append(account)
        assert accounts[0]["Id"] == "123456789012"


# --- MultiAccountStrategy ---
@pytest.mark.asyncio
async def test_multi_account_strategy_sanity_check_success():
    config = {
        "aws_access_key_id": "x",
        "aws_secret_access_key": "y",
        "organization_role_arn": [
            "arn:aws:iam::123456789012:role/OrgRole1",
            "arn:aws:iam::123456789012:role/OrgRole2",
        ],
    }
    provider = AssumeRoleProvider(config)
    strategy = MultiAccountStrategy(provider)

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
        result = await strategy.sanity_check()
        assert result is True
        assert len(strategy._valid_arns) == 2


# --- SessionStrategyFactory ---
@pytest.mark.asyncio
async def test_session_strategy_factory_single(monkeypatch, ocean_context):
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    ocean_context(config)

    async def async_true(self):
        return True

    monkeypatch.setattr(
        "aws.auth.account.SingleAccountStrategy.sanity_check", async_true
    )
    strategy = await SessionStrategyFactory.create()
    assert isinstance(strategy, SingleAccountStrategy)
