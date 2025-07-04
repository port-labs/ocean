from typing import Any, AsyncIterator, Optional, Tuple, Union
import asyncio

from loguru import logger
from port_ocean.context.ocean import ocean
from starlette.requests import Request
from aiobotocore.session import AioSession

from aws.auth.strategies.base import AWSSessionStrategy
from aws.auth.region_resolver import RegionResolver
from utils.overrides import AWSDescribeResourcesSelector
from aws.auth.session_factory import SessionStrategyFactory
from aws.auth.utils import CredentialsProviderError


# Private module-level state - using Union to be explicit about the uninitialized state
_session_strategy: Union[AWSSessionStrategy, None] = None
_session_lock = asyncio.Lock()


async def initialize_aws_credentials() -> bool:
    global _session_strategy

    logger.info("[AWS Init] Starting AWS authentication initialization")
    async with _session_lock:
        if _session_strategy is not None:
            logger.info("[AWS Init] Already initialized, skipping.")
            return True
        strategy = await SessionStrategyFactory.create()
        _session_strategy = strategy
        logger.debug(
            "Created session strategy successfully using validated credentials"
        )
        health_ok = await strategy.healthcheck()
        if not health_ok:
            logger.error("Sanity check failed during AWS authentication initialization")
            _session_strategy = None
            return False
        logger.info("AWS authentication system initialized successfully")
        return True


async def get_initialized_session_strategy() -> AWSSessionStrategy:
    if _session_strategy is None:
        await initialize_aws_credentials()
    if _session_strategy is None:
        raise CredentialsProviderError("Failed to initialize AWS credentials/session.")
    return _session_strategy


async def get_accounts() -> AsyncIterator[dict[str, Any]]:
    """Get accessible AWS accounts asynchronously."""
    strategy = await get_initialized_session_strategy()
    async for account in strategy.get_accessible_accounts():
        yield account


async def get_account_session(arn: str) -> Optional[AioSession]:
    """Get a single session for a specific ARN."""
    strategy = await get_initialized_session_strategy()
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


async def _fetch_account_session_with_semaphore(
    account: dict[str, Any], semaphore: asyncio.Semaphore
) -> Optional[tuple[dict[str, Any], AioSession]]:
    async with semaphore:
        session = await get_account_session(account["Arn"])
        if session:
            return (account, session)
    return None


async def get_all_account_sessions(
    concurrency: int = 10,
) -> AsyncIterator[tuple[dict[str, Any], AioSession]]:
    """Yield (account, session) tuples for all accessible AWS accounts concurrently, with controlled concurrency."""
    semaphore = asyncio.Semaphore(concurrency)
    tasks = []
    async for account in get_accounts():
        tasks.append(
            asyncio.create_task(
                _fetch_account_session_with_semaphore(account, semaphore)
            )
        )
    for task in asyncio.as_completed(tasks):
        result = await task
        if result:
            yield result
