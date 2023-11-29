import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx

from port_ocean.helpers.retry import RetryTransport

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient


class TokenRetryTransport(RetryTransport):
    def __init__(self, port_client: "PortClient", *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.port_client = port_client

    async def _handle_unauthorized(self, response: httpx.Response) -> None:
        token = await self.port_client.auth.token
        response.headers["Authorization"] = f"Bearer {token}"

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self._logger.info(
                "Got unauthorized response, trying to refresh token before retrying"
            )
            await self._handle_unauthorized(response)
            return True
        return await super()._should_retry_async(response)

    def _should_retry(self, response: httpx.Response) -> bool:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self._logger.info(
                "Got unauthorized response, trying to refresh token before retrying"
            )
            asyncio.get_running_loop().run_until_complete(
                self._handle_unauthorized(response)
            )

            return True
        return super()._should_retry(response)
