from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class SyncTier(StrEnum):
    """Cross-pod priority tier for centralized admission control."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RateLimitAcquireDecision(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class CentralizedRateLimitState:
    remaining: Optional[int] = None
    limit: Optional[int] = None
    reset_at: Optional[float] = None
    blocked_until: Optional[float] = None


@dataclass(frozen=True)
class AcquireResult:
    decision: RateLimitAcquireDecision
    wait_seconds: float = 0.0
