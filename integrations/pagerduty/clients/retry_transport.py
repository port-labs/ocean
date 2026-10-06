from http import HTTPStatus
from typing import Any

import httpx
from port_ocean.helpers.retry import RetryTransport

from clients.rate_limiter import PagerDutyRateLimiter, daily_quota_exhausted


class PagerDutyRetryTransport(RetryTransport):
    """Updates rate limits from each retry response and stops retrying 429s
    when the analytics daily quota is exhausted.

    Per-attempt updates help concurrent in-flight requests adapt early.
    """

    def __init__(self, *, rate_limiter: PagerDutyRateLimiter, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._rate_limiter = rate_limiter

    async def after_retry_async(
        self, request: httpx.Request, response: httpx.Response, attempt: int
    ) -> None:
        self._rate_limiter.update_rate_limits(response.headers, str(request.url))

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if (
            response.status_code == HTTPStatus.TOO_MANY_REQUESTS
            and daily_quota_exhausted(response.headers)
        ):
            return False
        return await super()._should_retry_async(response)
