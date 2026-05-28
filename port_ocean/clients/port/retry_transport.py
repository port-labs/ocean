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

    def is_token_error(self, response: httpx.Response) -> bool:
        return (
            response.status_code == HTTPStatus.UNAUTHORIZED
            and "/auth/access_token" not in str(response.request.url)
            and self.port_client.auth.last_token_object is not None
        )

    async def _refresh_request_authorization(
        self, request: httpx.Request
    ) -> httpx.Request:
        authorization = await self.port_client.auth.refresh_token()
        headers = httpx.Headers(
            [
                (key, value)
                for key, value in request.headers.items()
                if key.lower() != "authorization"
            ]
        )
        headers["Authorization"] = authorization
        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=request.content,
            extensions=request.extensions,
        )

    async def before_retry_async(
        self,
        request: httpx.Request,
        response: httpx.Response | None,
        sleep_time: float,
        attempt: int,
    ) -> httpx.Request | None:
        if response is not None and self.is_token_error(response):
            return await self._refresh_request_authorization(request)
        return None

    def _before_retry(
        self,
        request: httpx.Request,
        response: httpx.Response | None,
        sleep_time: float,
        attempt: int,
    ) -> httpx.Request | None:
        if response is not None and self.is_token_error(response):
            return asyncio.get_running_loop().run_until_complete(
                self._refresh_request_authorization(request)
            )
        return None

    async def _should_retry_async(self, response: httpx.Response) -> bool:
        if self.is_token_error(response):
            if self._logger:
                self._logger.info(
                    "Got unauthorized response, trying to refresh token before retrying"
                )
            return True
        return await super()._should_retry_async(response)

    def _should_retry(self, response: httpx.Response) -> bool:
        if self.is_token_error(response):
            if self._logger:
                self._logger.info(
                    "Got unauthorized response, trying to refresh token before retrying"
                )
            return True
        return super()._should_retry(response)
