from port_ocean.rate_limiting.backend import CentralizedRateLimiterBackend
from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    SyncTier,
)


class CentralizedRateLimiter:
    """Facade used by RetryTransport and (later) integration adapters."""

    def __init__(self, backend: CentralizedRateLimiterBackend) -> None:
        self._backend = backend

    @property
    def backend(self) -> CentralizedRateLimiterBackend:
        return self._backend

    async def acquire(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        tier: SyncTier,
    ) -> AcquireResult:
        return await self._backend.acquire(org_scope, integration_id, pool, tier)

    async def record_response(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        await self._backend.record_response(
            org_scope,
            integration_id,
            pool,
            state,
            is_rate_limited=is_rate_limited,
        )
