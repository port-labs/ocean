import asyncio
import random
import time
from datetime import datetime
from typing import Union, Mapping, Callable, Coroutine, Any

import httpx
from dateutil.parser import isoparse
from port_ocean.helpers.retry import RetryTransport

_ON_SENTRY_RETRY_CALLBACK: Callable[[httpx.Request], httpx.Request] | None = None


class SentryRetryTransport(RetryTransport):

    async def _retry_operation_async(
        self,
        request: httpx.Request,
        send_method: Callable[..., Coroutine[Any, Any, httpx.Response]],
    ) -> httpx.Response:
        remaining_attempts = self._max_attempts
        attempts_made = 0
        response: httpx.Response | None = None
        error: Exception | None = None
        while True:
            if attempts_made > 0:
                headers = response.headers if response and response.headers else {}
                sleep_time = self._calculate_sleep(attempts_made, headers)
                self._log_before_retry(request, sleep_time, response, error)
                await asyncio.sleep(sleep_time)

            error = None
            response = None
            try:
                response = await send_method(request)
                response.request = request
                if remaining_attempts < 1 or not (
                    await self._should_retry_async(response)
                ):
                    return response
                await response.aclose()
            except httpx.ConnectTimeout as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.ReadTimeout as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.TimeoutException as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            except httpx.HTTPError as e:
                error = e
                if remaining_attempts < 1:
                    self._log_error(request, error)
                    raise
            if _ON_SENTRY_RETRY_CALLBACK:
                request = _ON_SENTRY_RETRY_CALLBACK(request)
            attempts_made += 1
            remaining_attempts -= 1

    def _calculate_sleep(
        self, attempts_made: int, headers: Union[httpx.Headers, Mapping[str, str]]
    ) -> float:
        # The X-Sentry-Rate-Limit-Reset response HTTP header indicates how long the user agent should wait before
        # making a follow-up request.
        # When sent with a 429 (Too Many Requests) response, this indicates how long to wait before
        # making a new request.
        retry_after_header = (headers.get("X-Sentry-Rate-Limit-Reset") or "").strip()
        if self._respect_retry_after_header and retry_after_header:
            if self._respect_retry_after_header and retry_after_header:
                if retry_after_header.isdigit():
                    reset_timestamp = float(retry_after_header) / 1000
                    seconds_until_reset = reset_timestamp - time.time()
                    if seconds_until_reset < 0:
                        seconds_until_reset = 0
                    return seconds_until_reset

            try:
                parsed_date = isoparse(
                    retry_after_header
                ).astimezone()  # converts to local time
                diff = (parsed_date - datetime.now().astimezone()).total_seconds()
                if diff > 0:
                    return min(diff, self._max_backoff_wait)
            except ValueError:
                pass

        backoff = self._base_delay * (2 ** (attempts_made - 1))
        jitter = (backoff * self._jitter_ratio) * random.choice([1, -1])
        total_backoff = backoff + jitter
        return min(total_backoff, self._max_backoff_wait)
