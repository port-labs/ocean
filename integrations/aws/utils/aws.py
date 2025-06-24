from typing import Any, AsyncIterator, Optional
import asyncio

from loguru import logger
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from aiobotocore.session import AioSession

from aws.auth.account import AWSSessionStrategy
from aws.auth.credentials_provider import StaticCredentialProvider
from utils.overrides import AWSResourceConfig
from aws.auth.session_factory import SessionStrategyFactory


_session_strategy: AWSSessionStrategy
_validated_credentials = None
_session_lock = asyncio.Lock()


async def initialize_access_credentials() -> bool:
    """Initialize the new v2 authentication system."""
    global _session_strategy, _validated_credentials

    logger.info("[AWS Init] Starting AWS authentication initialization")
    async with _session_lock:
        _validated_credentials = StaticCredentialProvider(
            config=ocean.integration_config
        )
        validation_session = await _validated_credentials.get_session(None)
        async with validation_session.create_client("sts") as sts:
            identity = await sts.get_caller_identity()
            logger.info(
                f"Using AWS identity: arn={identity['Arn']}, account_id={identity['Account']}"
            )

        _session_strategy = await SessionStrategyFactory.create()
        logger.debug(
            "Created session strategy successfully using validated credentials"
        )
        logger.info("AWS authentication system initialized successfully")
        return True


async def get_accounts() -> AsyncIterator[dict[str, Any]]:
    """Get accessible AWS accounts asynchronously."""
    async for account in _session_strategy.get_accessible_accounts():
        yield account


async def get_sessions(
    resource_config: AWSResourceConfig,
    account_id: Optional[str] = None,
) -> AsyncIterator[tuple[AioSession, str]]:
    """Get AWS sessions for all accounts and regions for a given resource config."""
    if account_id:
        async for session_region_tuple in _session_strategy.create_session_for_account(
            account_id, resource_config
        ):
            yield session_region_tuple
    else:
        async for (
            session_region_tuple
        ) in _session_strategy.create_session_for_each_region(resource_config):
            yield session_region_tuple


async def get_session_for_account_and_region(
    account_id: str, region: str, resource_config: AWSResourceConfig
) -> Optional[tuple[AioSession, str]]:
    """Get a specific AWS session for a given account and region for a given resource config."""
    async for session, session_region in _session_strategy.create_session_for_account(
        account_id, resource_config
    ):
        if session_region == region:
            return session, session_region
    return None


async def get_account_session(account_id: str) -> Optional[AioSession]:
    """Get a single session for a specific account."""
    return await _session_strategy.get_account_session(account_id)


def validate_request(request: Request) -> tuple[bool, str]:
    """Validate incoming webhook requests."""
    api_key = request.headers.get("x-port-aws-ocean-api-key")
    if not api_key:
        return (False, "API key not found in request headers")
    if not ocean.integration_config.get("live_events_api_key"):
        return (False, "API key not found in integration config")
    if api_key != ocean.integration_config.get("live_events_api_key"):
        return (False, "Invalid API key")
    return (True, "Request validated")
