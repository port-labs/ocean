from http import HTTPStatus
from typing import Any, Callable, Coroutine, Dict, Iterable, Optional, Union
import typing

import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryConfig, RetryTransport
from github.clients.rate_limiter.utils import is_rate_limit_response


# Floor for the 500-recovery page-size backoff. GitHub returns intermittent 500s
# on large list pages; we halve per_page on each retry down to this size before
# giving up, since smaller pages reliably succeed.
MIN_PAGE_SIZE = 25


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport with GitHub-specific behaviour:
    - Retries rate-limit 403 responses (GitHub sometimes uses 403 for quota exhaustion).
    - Awaits an async `rate_limit_notifier` in `after_retry_async` on each rate-limit
      response so the rate limiter acquires its lock inline before the retry sleep begins.
    - Refreshes auth headers via `token_refresher` in `before_retry_async` so long
      rate-limit sleeps never leave the retry carrying a stale or expired token.
    - On a 500, halves the request's `per_page` (and repositions `page` to the same
      offset) before each retry instead of replaying the identical doomed request,
      and stops retrying once `per_page` reaches MIN_PAGE_SIZE. GitHub fails large
      pages deterministically, so this avoids burning the full retry budget on
      requests that cannot succeed at their current size.
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

    def _reduced_page_url(
        self, request: httpx.Request, response: Optional[httpx.Response]
    ) -> httpx.URL:
        """Halve `per_page` (and reposition `page`) when retrying a 500.

        Returns the original URL unchanged when this is not a 500, when the
        request is not paginated, or when `per_page` is already at the floor.
        """
        if response is None or response.status_code != HTTPStatus.INTERNAL_SERVER_ERROR:
            return request.url

        url_params = request.url.params
        try:
            per_page = int(url_params["per_page"])
            # The first page request omits `page` (GitHub defaults to 1); later
            # requests follow the Link header, which includes it explicitly.
            page = int(url_params.get("page", 1))
        except (KeyError, ValueError):
            return request.url

        if per_page <= MIN_PAGE_SIZE:
            return request.url

        reduced_per_page = max(per_page // 2, MIN_PAGE_SIZE)
        # page N at size S covers the same items as page 2N-1 at size S/2, so the
        # offset is preserved across the halving — no items skipped or repeated.
        reduced_page = 2 * page - 1
        logger.warning(
            f"GitHub returned 500 for {request.method} {request.url.path} at "
            f"page={page} per_page={per_page}; retrying at page={reduced_page} "
            f"per_page={reduced_per_page}"
        )
        return request.url.copy_merge_params(
            {"per_page": str(reduced_per_page), "page": str(reduced_page)}
        )

    async def before_retry_async(
        self,
        request: httpx.Request,
        response: Optional[httpx.Response],
        sleep_time: float,
        attempt: int,
    ) -> Optional[httpx.Request]:
        url = self._reduced_page_url(request, response)

        headers = dict(request.headers)
        if self._token_refresher is not None:
            fresh_headers = await self._token_refresher()
            headers.update({k.lower(): v for k, v in fresh_headers.items()})
        elif url == request.url:
            # No token to refresh and no page-size change — keep the request as-is.
            return None

        try:
            content = request.content
        except httpx.RequestNotRead:
            if isinstance(request.stream, typing.AsyncIterable):
                await request.aread()
            else:
                request.read()
            content = request.content

        return httpx.Request(
            method=request.method,
            url=url,
            headers=headers,
            content=content,
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

    def _page_reduction_exhausted(self, response: httpx.Response) -> bool:
        """True for a 500 whose request is already paginated at the floor size.

        Once `per_page` is down to MIN_PAGE_SIZE there is nothing left to shrink,
        so further retries would just replay the same failing request — stop and
        let the 500 propagate.
        """
        if response.status_code != HTTPStatus.INTERNAL_SERVER_ERROR:
            return False
        try:
            per_page = int(response.request.url.params["per_page"])
        except (RuntimeError, KeyError, ValueError):
            return False
        return per_page <= MIN_PAGE_SIZE

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if self._page_reduction_exhausted(response):
            return False
        return await super()._should_retry_async(response) or is_rate_limit_response(
            response
        )

    def _should_retry(self, response: httpx.Response) -> bool:
        if self._page_reduction_exhausted(response):
            return False
        return super()._should_retry(response) or is_rate_limit_response(response)
