from typing import Any, Callable, Coroutine, Dict, Iterable, Optional, Union

import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryConfig, RetryTransport
from github.clients.rate_limiter.utils import is_rate_limit_response


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport with GitHub-specific behaviour:
    - Retries rate-limit 403 responses (GitHub sometimes uses 403 for quota exhaustion).
    - Awaits an async `rate_limit_notifier` in `after_retry_async` on each rate-limit
      response so the rate limiter acquires its lock inline before the retry sleep begins.
    - Refreshes auth headers via `token_refresher` in `before_retry_async` so long
      rate-limit sleeps never leave the retry carrying a stale or expired token.
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
        token_refresher: Optional[
            Callable[[], Coroutine[Any, Any, Dict[str, str]]]
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
        self._token_refresher = token_refresher

    async def before_retry_async(
        self,
        request: httpx.Request,
        response: Optional[httpx.Response],
        sleep_time: float,
        attempt: int,
    ) -> Optional[httpx.Request]:
        if self._token_refresher is None:
            return None
        fresh_headers = await self._token_refresher()
        fresh_lower = {k.lower(): v for k, v in fresh_headers.items()}
        return httpx.Request(
            method=request.method,
            url=request.url,
            headers={**dict(request.headers), **fresh_lower},
            content=request.content,
            extensions=request.extensions,
        )

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
                f"GitHub rate limit hit — retrying {request.method} {request.url} in {sleep_time}s"
            )
        super()._log_before_retry(request, sleep_time, response, error)

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        return await super()._should_retry_async(response) or is_rate_limit_response(
            response
        )

    def _should_retry(self, response: httpx.Response) -> bool:
        return super()._should_retry(response) or is_rate_limit_response(response)
