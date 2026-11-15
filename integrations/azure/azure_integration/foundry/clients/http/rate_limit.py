from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

# ARM only reports remaining counts (no limit). Treat the pool as low below this.
_ARM_REMAINING_FLOOR = 20

# Fallback wait when a reset/retry header is missing or unparseable.
_DEFAULT_RESET_SECONDS = 10.0


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
    """Defer on 429 Retry-After and ARM remaining-floor headers.

    # ponytail: no Foundry soft RPM headroom — Azure catalog APIs don't expose it;
    # agent actions defer only on hard 429.
    """

    def __init__(self) -> None:
        self._hard_block_until: float = 0.0
        self._arm_block_until: float = 0.0

    def observe(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            self._hard_block_until = time.time() + _retry_after_seconds(
                response.headers
            )
            return

        self._hard_block_until = 0.0
        self._update_arm_block(response.headers)

    def hard_block_seconds(self) -> float:
        return max(0.0, self._hard_block_until - time.time())

    def is_close_to_rate_limit(self) -> bool:
        return self.seconds_until_rate_limit_reset() > 0

    def seconds_until_rate_limit_reset(self) -> float:
        now = time.time()
        waits: list[float] = []
        if now < self._hard_block_until:
            waits.append(self._hard_block_until - now)
        if now < self._arm_block_until:
            waits.append(self._arm_block_until - now)
        return max(waits, default=0.0)

    def _update_arm_block(self, headers: httpx.Headers) -> None:
        remaining = _min_arm_remaining(headers)
        if remaining is None:
            return
        self._arm_block_until = (
            time.time() + _DEFAULT_RESET_SECONDS
            if remaining < _ARM_REMAINING_FLOOR
            else 0.0
        )
