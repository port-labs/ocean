import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx

from port_ocean.helpers.retry import RetryTransport

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient


class TokenRetryTransport(RetryTransport):
    def __init__(self, port_client: "PortClient", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.port_client = port_client

    async def _handle_unauthorized(self, response: httpx.Response) -> None:
        token = await self.port_client.auth.token
        response.headers["Authorization"] = f"Bearer {token}"

    def is_token_error(self, response: httpx.Response) -> bool:
        return (
            response.status_code == HTTPStatus.UNAUTHORIZED
            and "/auth/access_token" not in str(response.request.url)
            and self.port_client.auth.last_token_object is not None
            and self.port_client.auth.last_token_object.expired
        )

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if self.is_token_error(response):
            if self._logger:
                self._logger.info(
                    "Got unauthorized response, trying to refresh token before retrying"
                )
            await self._handle_unauthorized(response)
            return True
        return await super()._should_retry_async(response)

    def _should_retry(self, response: httpx.Response) -> bool:
        if self.is_token_error(response):
            if self._logger:
                self._logger.info(
                    "Got unauthorized response, trying to refresh token before retrying"
                )
            asyncio.get_running_loop().run_until_complete(
                self._handle_unauthorized(response)
            )

            return True
        return super()._should_retry(response)
