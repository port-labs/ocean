from __future__ import annotations

from typing import Any, TypeVar

import httpx
from loguru import logger
from port_ocean.utils import http_async_client
from pydantic.v1 import BaseModel, ValidationError

from factory_ai.clients.exceptions import FactoryAIError

TResponse = TypeVar("TResponse", bound=BaseModel)


class FactoryClient:
    """HTTP transport for the Factory Public API.

    Auth: Bearer token (Factory API key). Base URL: https://api.factory.ai
    See https://docs.factory.com/api-reference

    Resource-specific fetch logic belongs in exporters, not here. This client
    only exposes generic request helpers that exporters compose against.
    """

    def __init__(
        self,
        api_host: str,
        api_key: str,
        request_timeout_seconds: int = 60,
    ) -> None:
        self._client = http_async_client
        self._base_url = api_host.rstrip("/")
        self._request_timeout_seconds = request_timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    @property
    def base_url(self) -> str:
        return self._base_url

    async def send_api_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        url = f"{self._base_url}{path}"
        response = await self._client.request(
            method=method,
            url=url,
            headers=self._headers,
            params=params,
            json=json_body,
            timeout=self._request_timeout_seconds,
        )
        if allow_not_found and response.status_code == 404:
            logger.warning(f"HTTP 404 for {method} {url}")
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            message = (
                f"HTTP {response.status_code} for {method} {url}: "
                f"{response.text[:200]}"
            )
            logger.error(message)
            raise httpx.HTTPStatusError(
                message, request=error.request, response=error.response
            ) from error
        if not response.content:
            return {}
        return response.json()

    async def get(
        self,
        path: str,
        response_model: type[TResponse],
        params: dict[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> TResponse | None:
        """GET ``path`` and validate the JSON body as ``response_model``."""
        payload = await self.send_api_request(
            "GET", path, params=params, allow_not_found=allow_not_found
        )
        if payload is None:
            return None
        try:
            return response_model.parse_obj(payload)
        except ValidationError as error:
            message = f"Invalid Factory response for GET {path}: {error}"
            logger.error(message)
            raise FactoryAIError(message) from error
