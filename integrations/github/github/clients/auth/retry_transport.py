import httpx

from port_ocean.helpers.retry import RetryTransport
from github.helpers.utils import has_exhausted_rate_limit_headers


class GitHubRetryTransport(RetryTransport):
    """
    Extends the default Ocean retry transport to also retry GitHub 403 responses
    that are clearly rate-limit related (based on GitHub rate limit headers).
    """

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
