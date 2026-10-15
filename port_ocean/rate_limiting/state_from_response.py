import time
from http import HTTPStatus
from typing import Optional

import httpx
from dateutil.parser import isoparse

from port_ocean.rate_limiting.models import CentralizedRateLimitState

_REMAINING_HEADERS = (
    "x-ratelimit-remaining",
    "ratelimit-remaining",
    "x-rate-limit-remaining",
)
_LIMIT_HEADERS = (
    "x-ratelimit-limit",
    "ratelimit-limit",
    "x-rate-limit-limit",
)
_RESET_HEADERS = (
    "x-ratelimit-reset",
    "ratelimit-reset",
    "x-rate-limit-reset",
    "x-ratelimit-resettime",
)
_RETRY_AFTER_HEADERS = ("retry-after",)


def _first_header(headers: httpx.Headers, names: tuple[str, ...]) -> Optional[str]:
    for name in names:
        value = (headers.get(name) or "").strip()
        if value:
            return value
    return None


def _parse_int(value: str) -> Optional[int]:
    try:
        return int(value)
    except ValueError:
        return None


def _parse_reset_to_epoch(header_value: str) -> Optional[float]:
    if header_value.isdigit():
        value = int(header_value)
        now = time.time()
        if value > 10_000:
            return float(value)
        return now + value
    try:
        parsed = isoparse(header_value).timestamp()
        return parsed
    except ValueError:
        return None


def rate_limit_state_from_response(
    response: httpx.Response,
) -> Optional[CentralizedRateLimitState]:
    """Best-effort vendor-agnostic header parsing until integrations supply adapters."""
    headers = response.headers
    remaining_raw = _first_header(headers, _REMAINING_HEADERS)
    limit_raw = _first_header(headers, _LIMIT_HEADERS)
    reset_raw = _first_header(headers, _RESET_HEADERS)
    retry_after_raw = _first_header(headers, _RETRY_AFTER_HEADERS)

    remaining = _parse_int(remaining_raw) if remaining_raw else None
    limit = _parse_int(limit_raw) if limit_raw else None
    reset_at = _parse_reset_to_epoch(reset_raw) if reset_raw else None

    blocked_until: Optional[float] = None
    if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
        if retry_after_raw and retry_after_raw.isdigit():
            blocked_until = time.time() + int(retry_after_raw)
        elif reset_at is not None:
            blocked_until = reset_at

    if (
        remaining is None
        and limit is None
        and reset_at is None
        and blocked_until is None
    ):
        return None

    return CentralizedRateLimitState(
        remaining=remaining,
        limit=limit,
        reset_at=reset_at,
        blocked_until=blocked_until,
    )
