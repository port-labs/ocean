from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

# New action runs back off once remaining quota is below this fraction of the limit.
_HEADROOM = 0.1
# ARM reports remaining counts without a limit. Below this, treat the pool as low.
_ARM_REMAINING_FLOOR = 20
_ARM_RESET_SECONDS = 10.0

_POOLS = (
    (
        "x-ratelimit-limit-requests",
        "x-ratelimit-remaining-requests",
        "x-ratelimit-reset-requests",
    ),
    (
        "x-ratelimit-limit-tokens",
        "x-ratelimit-remaining-tokens",
        "x-ratelimit-reset-tokens",
    ),
)


@dataclass(frozen=True)
class _Quota:
    limit: int
    remaining: int
    reset_at: float

    @property
    def seconds_until_reset(self) -> float:
        return max(0.0, self.reset_at - time.time())

    @property
    def is_low(self) -> bool:
        if self.limit <= 0 or self.seconds_until_reset <= 0:
            return False
        return self.remaining / self.limit < _HEADROOM


def _seconds_from_header(raw: str | None) -> float | None:
    """Seconds, ``Ns`` / ``Nms``, or an ISO timestamp. ``None`` when absent or unparseable."""
    if not raw or not raw.strip():
        return None
    value = raw.strip()
    lower = value.lower()
    try:
        if lower.endswith("ms"):
            return max(0.0, float(lower[:-2]) / 1000.0)
        if lower.endswith("s"):
            return max(0.0, float(lower[:-1]))
        if value.replace(".", "", 1).isdigit():
            return max(0.0, float(value))
        reset_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return max(0.0, (reset_at - datetime.now(timezone.utc)).total_seconds())
    except ValueError:
        return None


def _quota(
    headers: httpx.Headers, limit: str, remaining: str, reset: str
) -> _Quota | None:
    limit_raw = headers.get(limit)
    remaining_raw = headers.get(remaining)
    if limit_raw is None or remaining_raw is None:
        return None
    try:
        parsed_reset = _seconds_from_header(headers.get(reset))
        reset_seconds = _ARM_RESET_SECONDS if parsed_reset is None else parsed_reset
        return _Quota(
            limit=int(limit_raw),
            remaining=int(remaining_raw),
            reset_at=time.time() + reset_seconds,
        )
    except ValueError:
        return None


def _arm_remaining(headers: httpx.Headers) -> int | None:
    values = [
        int(value)
        for key, value in headers.items()
        if key.lower().startswith("x-ms-ratelimit-remaining") and value.isdigit()
    ]
    return min(values) if values else None


def _retry_after_seconds(headers: httpx.Headers) -> float:
    raw_ms = (headers.get("retry-after-ms") or "").strip()
    if raw_ms:
        try:
            return max(0.0, float(raw_ms) / 1000.0)
        except ValueError:
            pass
    for header in ("Retry-After", "x-ratelimit-reset-requests"):
        seconds = _seconds_from_header(headers.get(header))
        if seconds is not None:
            return seconds
    return _ARM_RESET_SECONDS


class FoundryRateLimiter:
    """Snapshot of Foundry and ARM rate-limit headers for action backoff."""

    def __init__(self) -> None:
        self._quotas: list[_Quota] = []
        self._blocked_until: float = 0.0
        self._arm_until: float = 0.0

    def observe(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            self._blocked_until = time.time() + _retry_after_seconds(response.headers)
            return

        self._blocked_until = 0.0
        quotas = [
            quota
            for limit, remaining, reset in _POOLS
            if (quota := _quota(response.headers, limit, remaining, reset)) is not None
        ]
        if quotas:
            self._quotas = quotas

        arm_remaining = _arm_remaining(response.headers)
        if arm_remaining is None:
            return
        self._arm_until = (
            time.time() + _ARM_RESET_SECONDS
            if arm_remaining < _ARM_REMAINING_FLOOR
            else 0.0
        )

    def _waits(self) -> list[float]:
        now = time.time()
        waits = [self._blocked_until - now] if now < self._blocked_until else []
        if now < self._arm_until:
            waits.append(self._arm_until - now)
        waits.extend(
            quota.seconds_until_reset for quota in self._quotas if quota.is_low
        )
        return waits

    def is_close_to_rate_limit(self) -> bool:
        return bool(self._waits())

    def seconds_until_rate_limit_reset(self) -> float:
        return max(self._waits(), default=0.0)
