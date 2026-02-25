import httpx
from loguru import logger

from port_ocean.helpers.retry import RetryTransport
from github.helpers.utils import has_exhausted_rate_limit_headers
from github.clients.rate_limiter.registry import GitHubRateLimiterRegistry


def _infer_github_api_type(path: str) -> str:
    """Infer GitHub API type from the request path."""
    if "/graphql" in path:
        return "graphql"
    if "/search" in path:
        return "search"
    return "rest"


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport to also retry GitHub 403 responses
    that are clearly rate-limit related (based on GitHub rate limit headers).
    """

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
            if self._is_rate_limit_response(response):
                self._notify_rate_limiter(request, response)
        super()._log_before_retry(request, sleep_time, response, error)

    def _is_rate_limit_response(self, response: httpx.Response) -> bool:
        """True if this response indicates a rate limit (429 or 403 with exhausted headers)."""
        return (
            response.status_code == 429
            or self._is_403_rate_limit(response)
        )

    def _notify_rate_limiter(
        self, request: httpx.Request, response: httpx.Response
    ) -> None:
        """Update the rate limiter immediately so other requests block until reset."""
        host = request.url.host or ""
        api_type = _infer_github_api_type(request.url.path or "")
        limiter = GitHubRateLimiterRegistry.get_limiter_if_exists(host, api_type)
        if limiter:
            resource = request.url.path or str(request.url)
            limiter.update_rate_limits(response.headers, resource)

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        return await super()._should_retry_async(response) or self._is_403_rate_limit(
            response
        )

    def _should_retry(self, response: httpx.Response) -> bool:
        return super()._should_retry(response) or self._is_403_rate_limit(response)

    def _is_403_rate_limit(self, response: httpx.Response) -> bool:
        """
        GitHub can respond with 403 for rate limits. Treat it as retryable only when
        the rate limit headers indicate an exhausted quota.
        """
        if response.status_code != 403:
            return False

        return has_exhausted_rate_limit_headers(response.headers)
