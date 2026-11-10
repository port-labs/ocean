from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import httpx
from azure.identity.aio import DefaultAzureCredential
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig

from azure_integration.foundry.clients.http.rate_limit import FoundryRateLimiter
from azure_integration.foundry.clients.http.retry_transport import (
    FOUNDRY_RETRY_AFTER_HEADERS,
    FoundryRetryTransport,
)
from azure_integration.foundry.helpers.utils import build_foundry_url

_FOUNDRY_SCOPE = "https://ai.azure.com/.default"
DEFAULT_FOUNDRY_API_VERSION = "v1"
# Cap error bodies so logs stay readable when Azure returns a large HTML/JSON payload.
_ERROR_BODY_LIMIT = 500

_client: FoundryHttpClient | None = None


class FoundryApiError(Exception):
    pass


class FoundryHttpClient:
    """HTTP client for Microsoft Foundry project data-plane APIs."""

    PAGE_SIZE = 100

    def __init__(
        self,
        *,
        api_version: str = DEFAULT_FOUNDRY_API_VERSION,
        page_size: int = PAGE_SIZE,
    ) -> None:
        self._api_version = api_version
        self._page_size = page_size
        self.rate_limiter = FoundryRateLimiter()
        self._credential: DefaultAzureCredential | None = None
        self._http = OceanAsyncClient(
            FoundryRetryTransport,
            retry_config=RetryConfig(retry_after_headers=FOUNDRY_RETRY_AFTER_HEADERS),
            timeout=httpx.Timeout(60.0),
            event_hooks={"response": [self._on_response]},
        )

    async def _on_response(self, response: httpx.Response) -> None:
        self.rate_limiter.observe(response)

    async def _authorization_headers(self) -> dict[str, str]:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def close(self) -> None:
        await self._http.aclose()
        if self._credential is not None:
            await self._credential.close()
            self._credential = None

    @staticmethod
    def uses_openai_compatible_routes(endpoint: str) -> bool:
        """Project ``openai/v1/*`` routes use path versioning, not ``api-version`` query."""
        return "/openai/v1/" in endpoint

    async def send_api_request(
        self,
        endpoint: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any]:
        query_params = dict(params or {})
        if not self.uses_openai_compatible_routes(endpoint):
            query_params.setdefault("api-version", self._api_version)
        headers = {
            **await self._authorization_headers(),
            **(extra_headers or {}),
        }
        response = await self._http.request(
            method,
            endpoint,
            params=query_params or None,
            json=json_body,
            headers=headers,
        )
        # Missing resource: GET/DELETE are empty; mutations must fail.
        if response.status_code == 404 and method.upper() in {"GET", "DELETE"}:
            return {}
        if response.is_error:
            detail = (
                response.text[:_ERROR_BODY_LIMIT]
                if response.text
                else response.reason_phrase
            )
            raise FoundryApiError(f"Foundry API {response.status_code}: {detail}")
        if not response.content:
            return {}
        payload = response.json()
        if isinstance(payload, (list, dict)):
            return payload
        return {}

    @staticmethod
    def items_from_payload(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        for key in ("data", "value", "items"):
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    @staticmethod
    def next_link(payload: dict[str, Any] | list[Any]) -> str | None:
        # Deployments (and other project ARM-style lists) use camelCase nextLink.
        if not isinstance(payload, dict):
            return None
        link = payload.get("nextLink")
        return link if isinstance(link, str) and link else None

    async def send_cursor_paginated_request(
        self,
        project_endpoint: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        request_params = dict(params or {})
        request_params.setdefault("limit", self._page_size)
        url = build_foundry_url(project_endpoint, path)
        while True:
            payload = await self.send_api_request(
                url, params=request_params, extra_headers=extra_headers
            )
            batch = self.items_from_payload(payload)
            if batch:
                yield batch
            if not isinstance(payload, dict) or not payload.get("has_more"):
                break
            last_id = payload.get("last_id")
            if not last_id:
                break
            request_params["after"] = last_id

    async def send_paginated_request(
        self,
        project_endpoint: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        request_params = dict(params or {})
        request_params.setdefault("limit", self._page_size)
        url = build_foundry_url(project_endpoint, path)
        while url:
            payload = await self.send_api_request(
                url, params=request_params, extra_headers=extra_headers
            )
            batch = self.items_from_payload(payload)
            if batch:
                yield batch
            next_url = self.next_link(payload) if isinstance(payload, dict) else None
            if not next_url:
                break
            url = next_url
            request_params = {}


def create_foundry_client(
    api_version: str = DEFAULT_FOUNDRY_API_VERSION,
) -> FoundryHttpClient:
    global _client
    if _client is None:
        _client = FoundryHttpClient(api_version=api_version)
    return _client


async def clear_foundry_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
    _client = None
