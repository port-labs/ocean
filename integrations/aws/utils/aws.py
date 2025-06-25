from typing import Any, AsyncIterator, Optional, Tuple, Union
import asyncio

from loguru import logger
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from aiobotocore.session import AioSession

from aws.auth.account import AWSSessionStrategy, RegionResolver
from utils.overrides import AWSDescribeResourcesSelector
from aws.auth.session_factory import SessionStrategyFactory
from aws.auth.utils import CredentialsProviderError, AWSSessionError


# Private module-level state - using Union to be explicit about the uninitialized state
_session_strategy: Union[AWSSessionStrategy, None] = None
_session_lock = asyncio.Lock()


async def initialize_aws_credentials() -> bool:
    """Initialize the new v2 authentication system."""
    global _session_strategy

    logger.info("[AWS Init] Starting AWS authentication initialization")
    async with _session_lock:
        strategy = await SessionStrategyFactory.create()
        logger.debug(
            "Created session strategy successfully using validated credentials"
        )
        sanity_ok = await strategy.sanity_check()
        if not sanity_ok:
            logger.error("Sanity check failed during AWS authentication initialization")
            return False
        _session_strategy = strategy
        logger.info("AWS authentication system initialized successfully")
        return True


async def get_credential_session() -> AWSSessionStrategy:
    if _session_strategy is None:
        await initialize_aws_credentials()
    if _session_strategy is None:
        raise CredentialsProviderError("Failed to initialize AWS credentials/session.")
    return _session_strategy


async def get_accounts() -> AsyncIterator[dict[str, Any]]:
    """Get accessible AWS accounts asynchronously."""
    strategy = await get_credential_session()
    async for account in strategy.get_accessible_accounts():
        yield account


async def get_sessions(
    selector: AWSDescribeResourcesSelector,
    arn: Optional[str] = None,
) -> AsyncIterator[Tuple[AioSession, str]]:
    """Get AWS sessions for all accounts and allowed regions, or for a specific ARN if provided. Handles region discovery internally."""
    strategy = await get_credential_session()
    if arn:
        async for session, region in strategy.create_session_for_account(arn, selector):
            yield session, region
    else:
        async for session, region in strategy.create_session_for_each_account(selector):
            yield session, region


async def get_account_session(arn: str) -> Optional[AioSession]:
    """Get a single session for a specific ARN."""
    strategy = await get_credential_session()
    return await strategy.get_account_session(arn)


def validate_request(request: Request) -> Tuple[bool, str]:
    """Validate incoming webhook requests."""
    api_key = request.headers.get("x-port-aws-ocean-api-key")
    if not api_key:
        return (False, "API key not found in request headers")
    if not ocean.integration_config.get("live_events_api_key"):
        return (False, "API key not found in integration config")
    if api_key != ocean.integration_config.get("live_events_api_key"):
        return (False, "Invalid API key")
    return (True, "Request validated")


async def get_allowed_regions(
    session: AioSession,
    selector: AWSDescribeResourcesSelector,
    region: Optional[str] = None,
) -> list[str]:
    """Get allowed regions using an existing session."""
    if region and selector.is_region_allowed(region):
        return [region]
    resolver = RegionResolver(session, selector)
    regions = await resolver.get_allowed_regions()
    return list(regions)


async def get_arn_for_account_id(account_id: str) -> Optional[str]:
    """Get ARN for a given account ID."""
    async for account in get_accounts():
        if account["Id"] == account_id:
            return account["Arn"]
    return None
