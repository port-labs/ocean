import time
from dataclasses import dataclass


@dataclass(frozen=True)
class LinearRateLimitStatus:
    requests_remaining: int | None
    complexity_remaining: int | None
    requests_reset_at_ms: int | None
    complexity_reset_at_ms: int | None

    def is_close_to_limit(self) -> bool:
        if self.requests_remaining is not None and self.requests_remaining < 20:
            return True
        if self.complexity_remaining is not None and self.complexity_remaining < 5_000:
            return True
        return False

    def seconds_until_reset(self) -> float:
        now_ms = int(time.time() * 1000)
        reset_times = [
            reset_at
            for reset_at in (self.requests_reset_at_ms, self.complexity_reset_at_ms)
            if reset_at is not None and reset_at > now_ms
        ]
        if not reset_times:
            return 0.0
        return max(0.0, (min(reset_times) - now_ms) / 1000)


def _parse_int_header(headers: dict[str, str], name: str) -> int | None:
    value = headers.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_rate_limit_headers(headers: dict[str, str]) -> LinearRateLimitStatus:
    normalized = {key.lower(): value for key, value in headers.items()}
    return LinearRateLimitStatus(
        requests_remaining=_parse_int_header(
            normalized, "x-ratelimit-requests-remaining"
        ),
        complexity_remaining=_parse_int_header(
            normalized, "x-ratelimit-complexity-remaining"
        ),
        requests_reset_at_ms=_parse_int_header(
            normalized, "x-ratelimit-requests-reset"
        ),
        complexity_reset_at_ms=_parse_int_header(
            normalized, "x-ratelimit-complexity-reset"
        ),
    )
