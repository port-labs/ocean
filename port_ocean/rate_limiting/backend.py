from abc import ABC, abstractmethod

from port_ocean.rate_limiting.models import (
    AcquireResult,
    CentralizedRateLimitState,
    SyncTier,
)


class CentralizedRateLimiterBackend(ABC):
    @abstractmethod
    async def acquire(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        tier: SyncTier,
    ) -> AcquireResult:
        raise NotImplementedError

    @abstractmethod
    async def record_response(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        raise NotImplementedError


class NoOpCentralizedRateLimiterBackend(CentralizedRateLimiterBackend):
    async def acquire(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        tier: SyncTier,
    ) -> AcquireResult:
        from port_ocean.rate_limiting.models import RateLimitAcquireDecision

        return AcquireResult(decision=RateLimitAcquireDecision.ALLOW)

    async def record_response(
        self,
        org_scope: str,
        integration_id: str,
        pool: str,
        state: CentralizedRateLimitState,
        *,
        is_rate_limited: bool = False,
    ) -> None:
        return None
