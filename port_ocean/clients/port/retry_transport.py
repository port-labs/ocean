import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import httpx
from loguru import logger as loguru_logger

from port_ocean.helpers.retry import RetryTransport

if TYPE_CHECKING:
    from port_ocean.clients.port.client import PortClient


class TokenRetryTransport(RetryTransport):
    def __init__(self, port_client: "PortClient", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.port_client = port_client
        self._had_rate_limit: set[str] = set()

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

    async def after_retry_async(
        self,
        request: httpx.Request,
        response: httpx.Response,
        attempt: int,
    ) -> None:
        url_key = str(request.url)
        if response.status_code == 429:
            self._had_rate_limit.add(url_key)
        elif response.ok and url_key in self._had_rate_limit:
            self._had_rate_limit.discard(url_key)
            loguru_logger.info(
                f"[DAN][RATE-LIMIT-RETRY-SUCCEEDED] {request.method} {request.url} | "
                f"status={response.status_code} | attempt={attempt} | "
                "request succeeded after rate limit wait"
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
