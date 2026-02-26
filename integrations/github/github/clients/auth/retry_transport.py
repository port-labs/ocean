import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryTransport


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport.

    401 and 403 are NOT retried at the transport level — they are handled by
    the higher-level retry loop in AbstractGithubClient.make_request, which
    releases the rate-limiter semaphore between attempts and refreshes auth
    tokens on 401.
    """

    _NO_TRANSPORT_RETRY_CODES = frozenset({401, 403})

    def _log_before_retry(
        self,
        request: httpx.Request,
        sleep_time: float,
        response: httpx.Response | None,
        error: Exception | None,
    ) -> None:
        if response and response.headers:
            remaining = response.headers.get("x-ratelimit-remaining")
            limit = response.headers.get("x-ratelimit-limit")
            reset = response.headers.get("x-ratelimit-reset")
            if remaining is not None and limit is not None:
                reset_msg = f", resets at {reset}" if reset else ""
                rate_limit_obj = {
                    "remaining": int(remaining) if remaining is not None else None,
                    "limit": int(limit) if limit is not None else None,
                    "reset": int(reset) if reset is not None else None,
                    "method": request.method,
                    "url": str(request.url),
                    "sleep_time": sleep_time,
                }
                logger.bind(**rate_limit_obj).info(
                    f"GitHub rate limit: {remaining}/{limit} tokens remaining{reset_msg} — "
                    f"retrying {request.method} {request.url} in {sleep_time}s"
                )
        super()._log_before_retry(request, sleep_time, response, error)

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if response.status_code in self._NO_TRANSPORT_RETRY_CODES:
            return False
        return await super()._should_retry_async(response)

    def _should_retry(self, response: httpx.Response) -> bool:
        if response.status_code in self._NO_TRANSPORT_RETRY_CODES:
            return False
        return super()._should_retry(response)
