from typing import Any, Callable, Coroutine, Iterable, Optional, Union

import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryConfig, RetryTransport
from jira.rate_limiter import is_rate_limit_response


class JiraRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport with Jira-specific behaviour:
    - Notifies the rate limiter via ``after_retry_async`` on every intermediate
      429 response so that other concurrent requests can be proactively gated
      instead of independently retrying into an exhausted quota.
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
        rate_limit_notifier: Optional[
            Callable[[httpx.Response], Coroutine[Any, Any, None]]
        ] = None,
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

    async def after_retry_async(
        self,
        request: httpx.Request,
        response: httpx.Response,
        attempt: int,
    ) -> None:
        if is_rate_limit_response(response) and self._rate_limit_notifier:
            await self._rate_limit_notifier(response)

    def _log_before_retry(
        self,
        request: httpx.Request,
        sleep_time: float,
        response: Optional[httpx.Response],
        error: Optional[Exception],
    ) -> None:
        if response and is_rate_limit_response(response):
            logger.bind(
                remaining=response.headers.get("x-ratelimit-remaining"),
                limit=response.headers.get("x-ratelimit-limit"),
                reset=response.headers.get("x-ratelimit-reset"),
                method=request.method,
                url=str(request.url),
                sleep_time=sleep_time,
            ).warning(
                f"Jira rate limit hit — retrying {request.method} {request.url} in {sleep_time}s"
            )
        super()._log_before_retry(request, sleep_time, response, error)
