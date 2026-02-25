from typing import Any, Callable, Iterable, Optional, Union

import httpx

from port_ocean.helpers.retry import RetryConfig, RetryTransport
from github.helpers.utils import has_exhausted_rate_limit_headers


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport with GitHub-specific behaviour:
    - Retries rate-limit 403 responses (GitHub sometimes uses 403 for quota exhaustion).
    - Fires a sync `rate_limit_notifier` callback before each 429 retry sleep so the
      rate limiter can immediately pause all other in-flight coroutines.
    """

    def __init__(
        self,
        wrapped_transport: Union[httpx.BaseTransport, httpx.AsyncBaseTransport],
        max_attempts: int = 10,
        max_backoff_wait: float = 60.0,
        base_delay: float = 0.1,
        jitter_ratio: float = 0.1,
        respect_retry_after_header: bool = True,
        retryable_methods: Optional[Iterable[str]] = None,
        retry_status_codes: Optional[Iterable[int]] = None,
        retry_config: Optional[RetryConfig] = None,
        logger: Optional[Any] = None,
        rate_limit_notifier: Optional[Callable[[httpx.Response], None]] = None,
    ) -> None:
        super().__init__(
            wrapped_transport,
            max_attempts=max_attempts,
            max_backoff_wait=max_backoff_wait,
            base_delay=base_delay,
            jitter_ratio=jitter_ratio,
            respect_retry_after_header=respect_retry_after_header,
            retryable_methods=retryable_methods,
            retry_status_codes=retry_status_codes,
            retry_config=retry_config,
            logger=logger,
        )
        self._rate_limit_notifier = rate_limit_notifier

    def _log_before_retry(
        self,
        request: httpx.Request,
        sleep_time: float,
        response: Optional[httpx.Response],
        error: Optional[Exception],
    ) -> None:
        if response and self._rate_limit_notifier and response.status_code == 429:
            self._rate_limit_notifier(response)
        super()._log_before_retry(request, sleep_time, response, error)

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        return await super()._should_retry_async(response) or self._is_403_rate_limit(
            response
        )

    def _should_retry(self, response: httpx.Response) -> bool:
        return super()._should_retry(response) or self._is_403_rate_limit(response)

    def _is_403_rate_limit(self, response: httpx.Response) -> bool:
        if response.status_code != 403:
            return False
        return has_exhausted_rate_limit_headers(response.headers)
