import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, Callable, Dict
from aiobotocore.session import AioSession
from aws.auth.account import (
    SingleAccountStrategy,
    MultiAccountStrategy,
    RegionResolver,
)
from aws.auth.credentials_provider import (
    StaticCredentialProvider,
    AssumeRoleProvider,
    CredentialsProviderError,
)
from aws.auth.session_factory import SessionStrategyFactory
from aws.auth.session_manager import SessionManager, SessionCreationError
from utils.overrides import AWSResourceConfig
import port_ocean.context.ocean as ocean_mod


@pytest.mark.asyncio
async def test_session_strategy_factory_single(
    monkeypatch: pytest.MonkeyPatch, ocean_context: Callable[[Dict[str, Any]], None]
) -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    ocean_context(config)
    resource_config = MagicMock(spec=AWSResourceConfig)
    resource_config.selector = MagicMock()
    resource_config.config = config

    async def async_true(self: Any) -> bool:
        return True

    monkeypatch.setattr(
        "aws.auth.account.SingleAccountStrategy.sanity_check", async_true
    )
    strategy = await SessionStrategyFactory.create(resource_config)
    assert isinstance(strategy, SingleAccountStrategy)
    assert await strategy.sanity_check() is True


@pytest.mark.asyncio
async def test_session_strategy_factory_multi(
    monkeypatch: pytest.MonkeyPatch, ocean_context: Callable[[Dict[str, Any]], None]
) -> None:
    config = {
        "aws_access_key_id": "x",
        "aws_secret_access_key": "y",
        "organization_role_arn": "arn:aws:iam::123456789012:role/OrgRole",
        "account_read_role_name": "ReadRole",
    }
    ocean_context(config)

    resource_config = MagicMock(spec=AWSResourceConfig)
    resource_config.selector = MagicMock()
    resource_config.config = config

    async def async_true(self: Any) -> bool:
        return True

    monkeypatch.setattr(
        "aws.auth.account.MultiAccountStrategy.sanity_check", async_true
    )
    strategy = await SessionStrategyFactory.create(resource_config, config=config)
    assert isinstance(strategy, MultiAccountStrategy)
    assert await strategy.sanity_check() is True


@pytest.mark.asyncio
async def test_static_credential_provider_success() -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    provider = StaticCredentialProvider(config)
    creds = await provider.get_credentials(region=None)
    assert creds.access_key == "x"
    assert creds.secret_key == "y"
    session = await provider.get_session(region=None)
    assert isinstance(session, AioSession)


@pytest.mark.asyncio
async def test_static_credential_provider_missing() -> None:
    provider = StaticCredentialProvider({})
    with pytest.raises(CredentialsProviderError):
        await provider.get_credentials(region=None)


@pytest.mark.asyncio
async def test_assume_role_provider_missing_role_arn() -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    provider = AssumeRoleProvider(config)
    with pytest.raises(ValueError):
        await provider.get_credentials(region=None, role_arn=None)


@pytest.mark.asyncio
async def test_single_account_strategy_get_accessible_accounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    resource_config = MagicMock(spec=AWSResourceConfig)
    resource_config.selector = MagicMock()
    provider = StaticCredentialProvider(config)
    strategy = SingleAccountStrategy(provider)

    session_mock = AsyncMock(spec=AioSession)
    sts_client_mock = AsyncMock()
    sts_client_mock.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    session_mock.create_client.return_value.__aenter__.return_value = sts_client_mock

    monkeypatch.setattr(provider, "get_session", AsyncMock(return_value=session_mock))

    accounts = []
    async for account in strategy.get_accessible_accounts():
        accounts.append(account)
    assert accounts[0]["Id"] == "123456789012"


@pytest.mark.asyncio
async def test_single_account_strategy_sanity_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    resource_config = MagicMock(spec=AWSResourceConfig)
    resource_config.selector = MagicMock()
    provider = StaticCredentialProvider(config)
    strategy = SingleAccountStrategy(provider)

    session_mock = AsyncMock(spec=AioSession)
    sts_client_mock = AsyncMock()
    sts_client_mock.get_caller_identity.return_value = {
        "Account": "123456789012",
        "Arn": "arn:aws:iam::123456789012:user/test",
    }
    session_mock.create_client.return_value.__aenter__.return_value = sts_client_mock

    monkeypatch.setattr(provider, "get_session", AsyncMock(return_value=session_mock))

    assert await strategy.sanity_check() is True


@pytest.mark.asyncio
async def test_single_account_strategy_sanity_check_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = {"aws_access_key_id": "x", "aws_secret_access_key": "y"}
    resource_config = MagicMock(spec=AWSResourceConfig)
    resource_config.selector = MagicMock()
    provider = StaticCredentialProvider(config)
    strategy = SingleAccountStrategy(provider)

    monkeypatch.setattr(
        provider, "get_session", AsyncMock(side_effect=Exception("fail"))
    )

    with pytest.raises(Exception, match="fail"):
        await strategy.sanity_check()


@pytest.mark.asyncio
async def test_session_manager_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    credentials = MagicMock()
    session_manager = SessionManager(credentials, max_retries=2, retry_delay=0)
    from botocore.exceptions import ClientError

    credentials.provider.get_session = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "Test"}}, "op")
    )
    with pytest.raises(ClientError):
        await session_manager.get_session(region="us-west-2")


@pytest.mark.asyncio
async def test_session_manager_success(monkeypatch: pytest.MonkeyPatch) -> None:
    credentials = MagicMock()
    session_manager = SessionManager(credentials)
    session_mock = AsyncMock(spec=AioSession)
    credentials.provider.get_session = AsyncMock(return_value=session_mock)
    session = await session_manager.get_session(region="us-west-2")
    assert session is session_mock


@pytest.mark.asyncio
async def test_region_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock(spec=AioSession)
    selector = MagicMock()
    selector.is_region_allowed.return_value = True
    resolver = RegionResolver(session, selector)

    monkeypatch.setattr(
        resolver,
        "get_enabled_regions",
        AsyncMock(return_value=["us-east-1", "us-west-2"]),
    )

    allowed = await resolver.get_allowed_regions()
    assert allowed == {"us-east-1", "us-west-2"}
