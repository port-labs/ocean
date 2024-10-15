from http import HTTPStatus

from aiohttp import ClientResponse

from port_ocean.helpers.retry import RetryRequestClass


class TokenRetryRequestClass(RetryRequestClass):
    async def _handle_unauthorized(self) -> None:
        token = await self._session.port_client.auth.token
        self.headers["Authorization"] = f"Bearer {token}"

    def is_token_error(self, response: ClientResponse) -> bool:
        return (
                response.status == HTTPStatus.UNAUTHORIZED
                and "/auth/access_token" not in str(self.url)
                and self._session.port_client.auth.last_token_object is not None
                and self._session.port_client.auth.last_token_object.expired
        )

    async def _should_retry_async(self, response: ClientResponse) -> bool:
        if self.is_token_error(response):
            if self._logger:
                self._logger.info(
                    "Got unauthorized response, trying to refresh token before retrying"
                )
            await self._handle_unauthorized()
            return True
        return await super()._should_retry_async(response)
