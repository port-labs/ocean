from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urljoin

import httpx
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.auth.abstract_authenticator import AbstractAzureAuthenticator
from clients.http.base_client import BaseFoundryClient


class FoundryApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class FoundryHttpClient(BaseFoundryClient):
    """Generic HTTP client for Microsoft Foundry project data-plane APIs."""

    def __init__(
        self,
        *,
        authenticator: AbstractAzureAuthenticator,
        api_version: str,
        page_size: int = BaseFoundryClient.PAGE_SIZE,
    ) -> None:
        self._authenticator = authenticator
        self._api_version = api_version
        self._page_size = page_size
        self._http = OceanAsyncClient(timeout=httpx.Timeout(60.0))

    async def close(self) -> None:
        await self._http.aclose()
        if hasattr(self._authenticator, "close"):
            await self._authenticator.close()

    async def get_authorization_headers(self) -> dict[str, str]:
        return await self._authenticator.get_authorization_header()

    def build_url(self, project_endpoint: str, path: str) -> str:
        base = project_endpoint.rstrip("/") + "/"
        normalized_path = path.lstrip("/")
        return urljoin(base, normalized_path)

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
        if method.upper() in {"GET", "DELETE", "POST", "PATCH", "PUT"}:
            if not self.uses_openai_compatible_routes(endpoint):
                query_params.setdefault("api-version", self._api_version)
        headers = {
            **await self._authenticator.get_authorization_header(),
            **(extra_headers or {}),
        }
        response = await self._http.request(
            method,
            endpoint,
            params=query_params or None,
            json=json_body,
            headers=headers,
        )
        if response.status_code == 404:
            return {}
        if response.is_error:
            detail = response.text[:2000] if response.text else response.reason_phrase
            raise FoundryApiError(
                f"Foundry API {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        if not response.content:
            return {}
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
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
        if not isinstance(payload, dict):
            return None
        for key in ("next_link", "nextLink", "@odata.nextLink"):
            link = payload.get(key)
            if isinstance(link, str) and link:
                return link
        return None

    async def send_cursor_paginated_request(
        self,
        project_endpoint: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Paginate OpenAI-style list responses using ``after`` + ``has_more``."""
        request_params = dict(params or {})
        request_params.setdefault("limit", self._page_size)
        while True:
            url = self.build_url(project_endpoint, path)
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
        url = self.build_url(project_endpoint, path)
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

    async def open_responses_stream(
        self,
        invoke_url: str,
        body: dict[str, Any],
        *,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        headers = await self._authenticator.get_authorization_header()
        headers["Accept"] = "text/event-stream"
        stream_body = {**body, "stream": True}
        query_params = dict(params or {})
        if not self.uses_openai_compatible_routes(invoke_url):
            query_params.setdefault("api-version", self._api_version)
        response = await self._http.request(
            "POST",
            invoke_url,
            params=query_params or None,
            json=stream_body,
            headers=headers,
        )
        if response.is_error:
            detail = response.text[:2000] if response.text else response.reason_phrase
            raise FoundryApiError(
                f"Foundry stream {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        return response
