from __future__ import annotations

from typing import Mapping, Optional, Union

import httpx
from port_ocean.helpers.retry import RetryTransport

# Foundry / Azure OpenAI recommend this on 429 (milliseconds).
RETRY_AFTER_MS_HEADER = "retry-after-ms"

# Prefer vendor wait hints before Ocean's generic Retry-After / x-ratelimit-reset.
FOUNDRY_RETRY_AFTER_HEADERS = [
    "Retry-After",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
]


class FoundryRetryTransport(RetryTransport):
    """Ocean retry transport with Foundry ``retry-after-ms`` support.

    Ocean's generic parser treats digit header values as seconds. Foundry's
    ``retry-after-ms`` is milliseconds, so it must be converted before sleep.
    """

    def _calculate_sleep(
        self,
        attempts_made: int,
        headers: Union[httpx.Headers, Mapping[str, str]],
        status_code: Optional[int] = None,
    ) -> float:
        ignore_headers = (
            status_code is not None and self._ignore_retry_after_headers(status_code)
        )
        if self._retry_config.respect_retry_after_header and not ignore_headers:
            raw = (headers.get(RETRY_AFTER_MS_HEADER) or "").strip()
            if raw:
                try:
                    return self._apply_sync_tier_jitter(max(0.0, float(raw) / 1000.0))
                except ValueError:
                    pass
        return super()._calculate_sleep(attempts_made, headers, status_code)
