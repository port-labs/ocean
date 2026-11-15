from __future__ import annotations

from unittest.mock import MagicMock

import httpx
from port_ocean.helpers.retry import RetryConfig

from azure_integration.foundry.clients.http.retry_transport import (
    FOUNDRY_RETRY_AFTER_HEADERS,
    FoundryRetryTransport,
)


def _transport(*, apply_sync_tier_jitter: bool = False) -> FoundryRetryTransport:
    return FoundryRetryTransport(
        wrapped_transport=MagicMock(),
        retry_config=RetryConfig(
            retry_after_headers=FOUNDRY_RETRY_AFTER_HEADERS,
            apply_sync_tier_jitter=apply_sync_tier_jitter,
        ),
    )


def test_retry_after_ms_converted_to_seconds() -> None:
    transport = _transport()
    sleep = transport._calculate_sleep(
        1, httpx.Headers({"retry-after-ms": "2000"}), status_code=429
    )
    assert sleep == 2.0


def test_retry_after_seconds_still_honored() -> None:
    transport = _transport()
    sleep = transport._calculate_sleep(
        1, httpx.Headers({"Retry-After": "5"}), status_code=429
    )
    assert sleep == 5.0


def test_retry_after_ms_preferred_over_retry_after() -> None:
    transport = _transport()
    sleep = transport._calculate_sleep(
        1,
        httpx.Headers({"retry-after-ms": "1500", "Retry-After": "30"}),
        status_code=429,
    )
    assert sleep == 1.5


def test_invalid_retry_after_ms_falls_back() -> None:
    transport = _transport()
    sleep = transport._calculate_sleep(
        1,
        httpx.Headers({"retry-after-ms": "nope", "Retry-After": "4"}),
        status_code=429,
    )
    assert sleep == 4.0
