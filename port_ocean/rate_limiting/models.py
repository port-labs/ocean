from dataclasses import dataclass
from enum import StrEnum


class SyncTier(StrEnum):
    """Cross-pod priority tier for centralized admission control."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RateLimitAcquireDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


class RateLimitBlockReason(StrEnum):
    """Why ``acquire`` told this caller to wait.

    ``blocked_until`` is a real 429. ``sync_tier`` is the remaining-ratio
    ceiling for this pod's tier. ``quota_exhausted`` is the reserve script
    refusing the slot after admission had already allowed a try.
    """

    BLOCKED_UNTIL = "blocked_until"
    SYNC_TIER = "sync_tier"
    QUOTA_EXHAUSTED = "quota_exhausted"


@dataclass(frozen=True)
class CentralizedRateLimitState:
    remaining: int | None = None
    limit: int | None = None
    reset_at: float | None = None
    blocked_until: float | None = None


@dataclass(frozen=True)
class AcquireResult:
    decision: RateLimitAcquireDecision
    wait_seconds: float = 0.0
    reason: RateLimitBlockReason | None = None
    remaining: int | None = None
    limit: int | None = None
    reset_at: float | None = None
    blocked_until: float | None = None
