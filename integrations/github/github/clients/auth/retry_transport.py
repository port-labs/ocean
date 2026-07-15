import json
from typing import Any, Callable, Coroutine, Dict, Iterable, Optional, Union
import typing

import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryConfig, RetryTransport
from github.clients.constants import GRAPHQL_SENT_VARIABLES_EXTENSION
from github.clients.rate_limiter.utils import is_rest_rate_limit_response


# Gateway errors that signal a query exceeded GitHub's GraphQL execution budget:
# gateway timeouts (502/504) and the reverse proxy's client-closed 499. These
# drive both the page-size backoff and the GraphQL query fallback.
GATEWAY_TIMEOUT_STATUS_CODES = (502, 504, 499)

# All 5xx we recover from by shrinking the page size before each retry — the
# gateway timeouts plus a plain 500 (a generic server error, which gets page-size
# backoff but not the GraphQL query fallback, hence kept separate above).
RETRYABLE_5XX_STATUS_CODES = GATEWAY_TIMEOUT_STATUS_CODES + (500,)

# Floors for the 5xx-recovery page-size backoff. We shrink the page on each retry
# down to these sizes before giving up, since smaller pages reliably succeed.
MIN_REST_PAGE_SIZE = 25
MIN_GRAPHQL_PAGE_SIZE = 1
GRAPHQL_REDUCTION_SIZE = 5


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport with GitHub-specific behaviour:
    - Retries rate-limit 403 responses (GitHub sometimes uses 403 for quota exhaustion).
    - Awaits an async `rate_limit_notifier` in `after_retry_async` on each rate-limit
      response so the rate limiter acquires its lock inline before the retry sleep begins.
    - Refreshes auth headers via `token_refresher` in `before_retry_async` so long
      rate-limit sleeps never leave the retry carrying a stale or expired token.
    - On a retryable 5xx (see RETRYABLE_5XX_STATUS_CODES), shrinks the request's
      page size before each retry instead of replaying the identical doomed
      request — halving REST `per_page` (repositioning `page` to the same offset)
      or stepping down GraphQL `variables.first` — and stops retrying once the
      page size reaches its floor. GitHub fails large pages deterministically, so
      this avoids burning the full retry budget on requests that cannot succeed at
      their current size.
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

    async def _reduced_page_request(
        self, request: httpx.Request, response: Optional[httpx.Response]
    ) -> httpx.Request:
        """Shrink the page size when retrying a retryable 5xx.

        Returns the request unchanged when this is not a retryable 5xx, when the
        request is not paginated, or when the page size is already at the floor.
        """
        if response is None or response.status_code not in RETRYABLE_5XX_STATUS_CODES:
            return request

        if self._is_graphql_request(request):
            return await self._reduce_page_for_graphql(request)
        return self._reduce_page_for_rest(request)

    def _reduce_page_for_rest(self, request: httpx.Request) -> httpx.Request:
        per_page = self._paginated_per_page(request.url)
        if per_page is None or per_page <= MIN_REST_PAGE_SIZE:
            return request

        try:
            page = int(request.url.params.get("page", 1))
        except ValueError:
            return request

        reduced_per_page = max(per_page // 2, MIN_REST_PAGE_SIZE)
        # page N at size S covers the same items as page 2N-1 at size S/2, so the
        # offset is preserved across the halving — no items skipped or repeated.
        reduced_page = 2 * page - 1
        logger.warning(
            f"GitHub returned a server error for {request.method} "
            f"{request.url.path} at page={page} per_page={per_page}; "
            f"retrying at page={reduced_page} per_page={reduced_per_page}"
        )
        url = request.url.copy_merge_params(
            {"per_page": str(reduced_per_page), "page": str(reduced_page)}
        )
        return httpx.Request(
            method=request.method,
            url=url,
            headers=request.headers,
            content=request.content,
            extensions=request.extensions,
        )

    async def _reduce_page_for_graphql(self, request: httpx.Request) -> httpx.Request:
        current_page_size = self._graphql_first(request)
        if not current_page_size or current_page_size <= MIN_GRAPHQL_PAGE_SIZE:
            return request
        request_body = json.loads(await self._read_request_body(request))
        reduced_page_size = max(
            current_page_size - GRAPHQL_REDUCTION_SIZE, MIN_GRAPHQL_PAGE_SIZE
        )
        logger.warning(
            f"GitHub returned a server error for {request.method} "
            f"{request.url.path} at first={current_page_size}; "
            f"retrying at first={reduced_page_size}"
        )
        request_body["variables"]["first"] = reduced_page_size
        # Drop the original Content-Length so httpx recomputes it for the smaller
        # body; copying it verbatim would describe the wrong byte count.
        headers = {
            k: v for k, v in request.headers.items() if k.lower() != "content-length"
        }
        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=json.dumps(request_body),
            extensions=request.extensions,
        )

    async def _read_request_body(self, request: httpx.Request) -> bytes:
        try:
            content = request.content
        except httpx.RequestNotRead:
            if isinstance(request.stream, typing.AsyncIterable):
                await request.aread()
            else:
                request.read()
            content = request.content

        return content

    async def before_retry_async(
        self,
        request: httpx.Request,
        response: Optional[httpx.Response],
        sleep_time: float,
        attempt: int,
    ) -> Optional[httpx.Request]:
        request = await self._reduced_page_request(request, response)

        headers = dict(request.headers)
        if self._token_refresher is not None:
            fresh_headers = await self._token_refresher()
            headers.update({k.lower(): v for k, v in fresh_headers.items()})

        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=await self._read_request_body(request),
            extensions=request.extensions,
        )

    async def after_retry_async(
        self,
        request: httpx.Request,
        response: httpx.Response,
        attempt: int,
    ) -> None:
        if is_rest_rate_limit_response(response) and self._rate_limit_notifier:
            await self._rate_limit_notifier(response)

        if self._is_graphql_request(request):
            variables = self._graphql_variables(request)
            if variables is not None:
                response.extensions[GRAPHQL_SENT_VARIABLES_EXTENSION] = variables

    def _log_before_retry(
        self,
        request: httpx.Request,
        sleep_time: float,
        response: Optional[httpx.Response],
        error: Optional[Exception],
    ) -> None:
        if response and is_rest_rate_limit_response(response):
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

    @staticmethod
    def _paginated_per_page(url: httpx.URL) -> Optional[int]:
        """The `per_page` of a paginated request URL, or None if not paginated."""
        try:
            return int(url.params["per_page"])
        except (KeyError, ValueError):
            return None

    @staticmethod
    def _is_graphql_request(request: httpx.Request) -> bool:
        """True for GitHub's GraphQL endpoint.

        Matches on the path suffix rather than a substring of the full URL so a
        stray `graphql` in a query value can't be mistaken for the endpoint.
        """
        return request.url.path.endswith("graphql")

    @staticmethod
    def _graphql_first(request: httpx.Request) -> Optional[int]:
        """The `variables.first` of a GraphQL request body, or None if absent.

        GraphQL payloads are sent buffered (`json=`), so `request.content` is
        available without re-reading the stream.
        """
        try:
            first = json.loads(request.content).get("variables", {}).get("first")
        except (httpx.RequestNotRead, ValueError, AttributeError):
            return None
        return first if isinstance(first, int) else None

    @staticmethod
    def _graphql_variables(request: httpx.Request) -> Optional[Dict[str, Any]]:
        """The `variables` of a GraphQL request body, or None if unavailable.

        Read from the request the retry loop actually sent, so the value reflects
        any rewrite (e.g. a shrunk `first`) rather than the caller's original.
        """
        try:
            return json.loads(request.content).get("variables")
        except Exception:
            return None

    def _page_reduction_exhausted(self, response: httpx.Response) -> bool:
        """True for a retryable 5xx whose request is already at the page floor.

        Once the page size is down to its floor there is nothing left to shrink,
        so further retries would just replay the same failing request — stop and
        let the 5xx propagate. Requests we can't shrink (non-paginated REST, or a
        GraphQL request without `first`) are not exhausted here; they fall through
        to the normal retry policy.
        """
        if response.status_code not in RETRYABLE_5XX_STATUS_CODES:
            return False
        try:
            request = response.request
        except RuntimeError:
            # response carries no request.
            return False
        if self._is_graphql_request(request):
            first = self._graphql_first(request)
            return first is not None and first <= MIN_GRAPHQL_PAGE_SIZE
        per_page = self._paginated_per_page(request.url)
        return per_page is not None and per_page <= MIN_REST_PAGE_SIZE

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if self._page_reduction_exhausted(response):
            return False
        return await super()._should_retry_async(
            response
        ) or is_rest_rate_limit_response(response)

    def _should_retry(self, response: httpx.Response) -> bool:
        if self._page_reduction_exhausted(response):
            return False
        return super()._should_retry(response) or is_rest_rate_limit_response(response)
