import asyncio
import time
from http import HTTPStatus

import httpx
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.rate_limiting.constants import (
    CENTRALIZED_RATE_LIMIT_POOL_EXTENSION,
    DEFAULT_RATE_LIMIT_POOL,
    SKIP_CENTRALIZED_RATE_LIMIT_EXTENSION,
)
from port_ocean.rate_limiting.models import (
    CentralizedRateLimitState,
    RateLimitAcquireDecision,
)
from port_ocean.rate_limiting.registry import get_centralized_rate_limiter
from port_ocean.rate_limiting.scope import (
    rate_limit_integration_id,
    rate_limit_org_scope,
)
from port_ocean.rate_limiting.state_from_response import rate_limit_state_from_response
from port_ocean.rate_limiting.tier import derive_sync_tier


def _pool_for_request(request: httpx.Request) -> str:
    pool = request.extensions.get(CENTRALIZED_RATE_LIMIT_POOL_EXTENSION)
    if isinstance(pool, str) and pool:
        return pool
    return DEFAULT_RATE_LIMIT_POOL


def _skip_centralized(request: httpx.Request) -> bool:
    return bool(request.extensions.get(SKIP_CENTRALIZED_RATE_LIMIT_EXTENSION))


def _max_acquire_wait_seconds() -> float:
    try:
        return float(ocean.config.centralized_rate_limiter.max_acquire_wait_seconds)
    except Exception:
        return 3600.0


def _org_scope_override() -> str | None:
    try:
        return ocean.config.centralized_rate_limiter.org_scope
    except Exception:
        return None


def _is_enabled() -> bool:
    try:
        return bool(ocean.config.centralized_rate_limiter.enabled)
    except Exception:
        return False


async def await_centralized_rate_limit(request: httpx.Request) -> None:
    if _skip_centralized(request) or not _is_enabled():
        return

    limiter = get_centralized_rate_limiter()
    if limiter is None:
        return

    org_scope = rate_limit_org_scope(_org_scope_override())
    integration_id = rate_limit_integration_id()
    pool = _pool_for_request(request)
    tier = derive_sync_tier()
    max_wait = _max_acquire_wait_seconds()

    deadline = time.monotonic() + max_wait if max_wait > 0 else None

    while True:
        try:
            result = await limiter.acquire(org_scope, integration_id, pool, tier)
        except Exception as error:
            logger.warning(
                "Centralized rate limiter acquire error; allowing request",
                error=str(error),
            )
            return

        if result.decision == RateLimitAcquireDecision.ALLOW:
            return

        wait_seconds = result.wait_seconds
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning(
                    "Centralized rate limiter max_acquire_wait exceeded; sending anyway",
                    pool=pool,
                    tier=tier.value,
                )
                return
            wait_seconds = min(wait_seconds, remaining)

        if wait_seconds <= 0:
            return

        logger.debug(
            "Centralized rate limiter blocked request",
            pool=pool,
            tier=tier.value,
            wait_seconds=wait_seconds,
        )
        await asyncio.sleep(wait_seconds)


async def record_centralized_rate_limit_response(
    request: httpx.Request, response: httpx.Response
) -> None:
    if _skip_centralized(request) or not _is_enabled():
        return

    limiter = get_centralized_rate_limiter()
    if limiter is None:
        return

    state = rate_limit_state_from_response(response)
    if state is None and response.status_code != HTTPStatus.TOO_MANY_REQUESTS:
        return

    if state is None:
        state = CentralizedRateLimitState(blocked_until=time.time() + 60)

    org_scope = rate_limit_org_scope(_org_scope_override())
    integration_id = rate_limit_integration_id()
    pool = _pool_for_request(request)
    is_rate_limited = response.status_code == HTTPStatus.TOO_MANY_REQUESTS

    try:
        await limiter.record_response(
            org_scope,
            integration_id,
            pool,
            state,
            is_rate_limited=is_rate_limited,
        )
    except Exception as error:
        logger.warning(
            "Centralized rate limiter record_response error; continuing",
            error=str(error),
        )
