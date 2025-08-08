from httpx import Response
from port_ocean.helpers.retry import RetryTransport


class LaunchDarklyRetryTransport(RetryTransport):

    async def _should_retry_async(self, response: Response) -> bool:
        if response.status_code == 429:
            return False
        return response.status_code in self._retry_status_codes
