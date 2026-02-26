import random
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from loguru import logger

from github.clients.rate_limiter.limiter import GitHubRateLimiter


_ALWAYS_RETRYABLE_STATUS_CODES = frozenset({401, 500, 502, 503, 504})


@dataclass(frozen=True)
class ClientRetryConfig:
    max_attempts: int = 10
    base_delay: float = 1.0
    max_backoff_wait: float = 1800.0
    jitter_ratio: float = 0.1


class ClientRetryHandler:
    """Decides whether a failed GitHub request should be retried and how long to wait.

    Unlike the transport-level retry (which holds the rate-limiter semaphore
    during back-off sleeps), the client-level retry runs *outside* the
    semaphore so other coroutines can make progress while we wait for a
    rate-limit reset or token refresh.
    """

    def __init__(self, config: Optional[ClientRetryConfig] = None) -> None:
        self.config = config or ClientRetryConfig()

    def is_retryable(
        self,
        response: httpx.Response,
        rate_limiter: GitHubRateLimiter,
    ) -> bool:
        if response.status_code in _ALWAYS_RETRYABLE_STATUS_CODES:
            return True
        return rate_limiter.is_rate_limit_response(response)

    def calculate_sleep(self, attempt: int, response: httpx.Response) -> float:
        """Return the number of seconds to sleep before the next attempt.

        Prefers the ``x-ratelimit-reset`` / ``retry-after`` headers when
        present; falls back to exponential back-off with jitter otherwise.
        """
        header_sleep = self._sleep_from_headers(response)
        if header_sleep is not None:
            return min(header_sleep, self.config.max_backoff_wait)

        return self._exponential_backoff(attempt)

    def prepare_retry(
        self,
        response: httpx.Response,
        authenticator: object,
        attempt: int,
        resource: str,
    ) -> None:
        """Perform any side-effects needed before the next retry attempt."""
        if response.status_code == 401:
            if hasattr(authenticator, "cached_installation_token"):
                authenticator.cached_installation_token = None
            logger.warning(
                f"[RetryHandler] 401 on {resource} — "
                f"invalidated token cache (attempt {attempt + 1}/{self.config.max_attempts})"
            )
        elif self._is_rate_limit_status(response):
            logger.warning(
                f"[RetryHandler] rate-limited on {resource} — "
                f"status={response.status_code} "
                f"(attempt {attempt + 1}/{self.config.max_attempts})"
            )
        else:
            logger.warning(
                f"[RetryHandler] retryable error on {resource} — "
                f"status={response.status_code} "
                f"(attempt {attempt + 1}/{self.config.max_attempts})"
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_rate_limit_status(response: httpx.Response) -> bool:
        return response.status_code in (403, 429)

    @staticmethod
    def _sleep_from_headers(response: httpx.Response) -> Optional[float]:
        reset = response.headers.get("x-ratelimit-reset")
        if reset:
            try:
                wait = int(reset) - int(time.time())
                if wait > 0:
                    return float(wait)
            except (ValueError, TypeError):
                pass

        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except (ValueError, TypeError):
                pass

        return None

    def _exponential_backoff(self, attempt: int) -> float:
        backoff = self.config.base_delay * (2**attempt)
        jitter = backoff * self.config.jitter_ratio * random.choice([1, -1])
        return min(backoff + jitter, self.config.max_backoff_wait)
