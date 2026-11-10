from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

# Back off when remaining quota drops below this fraction of the limit.
_HEADROOM = 0.1

# ARM only reports remaining counts (no limit). Treat the pool as low below this.
_ARM_REMAINING_FLOOR = 20

# Fallback wait when a reset/retry header is missing or unparseable.
_DEFAULT_RESET_SECONDS = 10.0

# Foundry (OpenAI-style) request/token pools.
_FOUNDRY_POOLS = (
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


def _parse_duration_seconds(raw: str | None) -> float | None:
    """Parse a duration header: plain seconds, ``Ns`` / ``Nms``, or ISO timestamp."""
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


def _foundry_quota(
    headers: httpx.Headers, limit_key: str, remaining_key: str, reset_key: str
) -> _Quota | None:
    limit_raw = headers.get(limit_key)
    remaining_raw = headers.get(remaining_key)
    if limit_raw is None or remaining_raw is None:
        return None
    try:
        parsed_reset = _parse_duration_seconds(headers.get(reset_key))
        reset_seconds = _DEFAULT_RESET_SECONDS if parsed_reset is None else parsed_reset
        return _Quota(
            limit=int(limit_raw),
            remaining=int(remaining_raw),
            reset_at=time.time() + reset_seconds,
        )
    except ValueError:
        return None


def _min_arm_remaining(headers: httpx.Headers) -> int | None:
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
        seconds = _parse_duration_seconds(headers.get(header))
        if seconds is not None:
            return seconds
    return _DEFAULT_RESET_SECONDS


class FoundryRateLimiter:
    """Tracks Foundry and ARM rate-limit headers so actions can defer new runs."""

    def __init__(self) -> None:
        self._foundry_quotas: list[_Quota] = []
        self._hard_block_until: float = 0.0
        self._arm_block_until: float = 0.0

    def observe(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            self._hard_block_until = time.time() + _retry_after_seconds(
                response.headers
            )
            return

        self._hard_block_until = 0.0
        self._update_foundry_quotas(response.headers)
        self._update_arm_block(response.headers)

    def is_close_to_rate_limit(self) -> bool:
        return self.seconds_until_rate_limit_reset() > 0

    def seconds_until_rate_limit_reset(self) -> float:
        now = time.time()
        waits: list[float] = []
        if now < self._hard_block_until:
            waits.append(self._hard_block_until - now)
        if now < self._arm_block_until:
            waits.append(self._arm_block_until - now)
        waits.extend(
            quota.seconds_until_reset for quota in self._foundry_quotas if quota.is_low
        )
        return max(waits, default=0.0)

    def _update_foundry_quotas(self, headers: httpx.Headers) -> None:
        quotas = [
            quota
            for limit_key, remaining_key, reset_key in _FOUNDRY_POOLS
            if (quota := _foundry_quota(headers, limit_key, remaining_key, reset_key))
            is not None
        ]
        if quotas:
            self._foundry_quotas = quotas

    def _update_arm_block(self, headers: httpx.Headers) -> None:
        remaining = _min_arm_remaining(headers)
        if remaining is None:
            return
        self._arm_block_until = (
            time.time() + _DEFAULT_RESET_SECONDS
            if remaining < _ARM_REMAINING_FLOOR
            else 0.0
        )
