from typing import Any, AsyncIterator, Optional, Union, cast
import asyncio

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from starlette.requests import Request
from aiobotocore.session import AioSession

from aws.auth.account import AWSSessionStrategy
from aws.auth.credentials_provider import StaticCredentialProvider
from utils.overrides import AWSResourceConfig
from aws.auth.session_factory import SessionStrategyFactory


# Global session strategy and credentials with thread safety
_session_strategy: AWSSessionStrategy  # Eagerly initialized at startup
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
        temp_session = await _validated_credentials.get_session(None)
        async with temp_session.create_client("sts") as sts:
            identity = await sts.get_caller_identity()
            logger.info(
                "[AWS Init] Using AWS identity: arn=%s, account_id=%s",
                identity["Arn"],
                identity["Account"],
            )

        # Eagerly initialize session strategy
        resource_config = cast(AWSResourceConfig, event.resource_config)
        logger.debug("Using resource config from event context")
        _session_strategy = await SessionStrategyFactory.create(
            resource_config=resource_config
        )
        logger.debug(
            "Created session strategy successfully using validated credentials"
        )
        logger.info("[AWS Init] AWS authentication system initialized successfully")
        return True


async def get_accounts() -> AsyncIterator[dict[str, Any]]:
    """Get accessible AWS accounts asynchronously."""
    async for account in _session_strategy.get_accessible_accounts():
        yield account


async def get_sessions(
    account_id: Optional[str] = None,
) -> AsyncIterator[tuple[AioSession, str]]:
    """Get AWS sessions for all accounts and regions."""
    if account_id:
        async for session_region_tuple in _session_strategy.create_session_for_account(
            account_id
        ):
            yield session_region_tuple
    else:
        async for (
            session_region_tuple
        ) in _session_strategy.create_session_for_each_region():
            yield session_region_tuple


async def get_session_for_account_and_region(
    account_id: str, region: str
) -> Optional[tuple[AioSession, str]]:
    """Get a specific AWS session for a given account and region."""
    async for session, session_region in _session_strategy.create_session_for_account(
        account_id
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
