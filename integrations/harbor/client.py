"""Async Harbor API client built on Ocean's shared HTTP layer."""

from __future__ import annotations

import asyncio
import base64
import random
from enum import StrEnum
from time import perf_counter
from typing import Any, AsyncGenerator, Mapping
from urllib.parse import urljoin

try:  # pragma: no cover - fallback for test environments without httpx installed
    import httpx
    from httpx import Response
except ModuleNotFoundError:  # pragma: no cover
    from integrations.harbor._compat import httpx_stub as httpx
    from integrations.harbor._compat.httpx_stub import Response
from loguru import logger

from port_ocean.utils import http_async_client
from port_ocean.utils.cache import cache_iterator_result


class HarborAuthMode(StrEnum):
    """Supported authentication modes for Harbor."""

    ROBOT_TOKEN = "robot_token"
    BASIC = "basic"
    OIDC = "oidc"


class HarborClient:
    """Thin wrapper around http_async_client with Harbor-specific semantics."""

    RETRYABLE_STATUS = {401, 429}

    def __init__(
        self,
        base_url: str,
        auth_mode: str,
        *,
        robot_account: str | None = None,
        robot_token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        oidc_access_token: str | None = None,
        max_retries: int = 5,
        backoff_factor: float = 0.5,
        max_backoff_seconds: float = 30.0,
        default_timeout: float | None = None,
        max_concurrency: int | None = None,
        jitter_seconds: float = 0.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_mode = HarborAuthMode(auth_mode)
        self.robot_account = robot_account
        self.robot_token = robot_token
        self.username = username
        self.password = password
        self.oidc_access_token = oidc_access_token
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff_seconds = max_backoff_seconds
        self.default_timeout = default_timeout
        self._client = client or http_async_client
        self._semaphore = (
            asyncio.Semaphore(max_concurrency)
            if isinstance(max_concurrency, int) and max_concurrency > 0
            else None
        )
        self.jitter_seconds = max(jitter_seconds, 0.0)

    def _build_auth_header(self) -> Mapping[str, str]:
        if self.auth_mode is HarborAuthMode.ROBOT_TOKEN:
            if not (self.robot_account and self.robot_token):
                raise ValueError(
                    "robot_account and robot_token are required when auth_mode is 'robot_token'"
                )
            credentials = f"{self.robot_account}:{self.robot_token}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        if self.auth_mode is HarborAuthMode.BASIC:
            if not (self.username and self.password):
                raise ValueError(
                    "username and password are required when auth_mode is 'basic'"
                )
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}

        if self.auth_mode is HarborAuthMode.OIDC:
            if not self.oidc_access_token:
                raise ValueError(
                    "oidc_access_token must be provided when auth_mode is 'oidc'"
                )
            return {"Authorization": f"Bearer {self.oidc_access_token}"}

        return {}

    def _build_url(self, path: str) -> str:
        normalized_path = path.lstrip("/")
        return urljoin(f"{self.base_url}/", normalized_path)

    def _should_retry(self, status_code: int) -> bool:
        return status_code in self.RETRYABLE_STATUS or 500 <= status_code < 600

    def _get_backoff(self, attempt: int, retry_after_header: str | None) -> float:
        if retry_after_header:
            try:
                retry_after = float(retry_after_header)
                if retry_after >= 0:
                    return min(retry_after, self.max_backoff_seconds)
            except ValueError:
                pass

        backoff = min(
            self.backoff_factor * (2 ** (attempt - 1)), self.max_backoff_seconds
        )

        if self.jitter_seconds > 0 and retry_after_header is None:
            backoff = min(
                backoff + random.uniform(0, self.jitter_seconds),
                self.max_backoff_seconds,
            )

        return backoff

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Response:
        method_upper = method.upper()
        url = self._build_url(path)
        request_headers: dict[str, str] = {
            "Accept": "application/json",
            **self._build_auth_header(),
        }
        if headers:
            request_headers.update(headers)

        attempt = 0
        while True:
            attempt += 1
            start = perf_counter()

            try:

                async def _perform_request() -> Response:
                    return await self._client.request(
                        method=method_upper,
                        url=url,
                        params=params,
                        json=json,
                        headers=request_headers,
                        timeout=timeout or self.default_timeout,
                    )

                if self._semaphore is not None:
                    async with self._semaphore:
                        response = await _perform_request()
                else:
                    response = await _perform_request()

                latency_ms = (perf_counter() - start) * 1000
                log = logger.bind(
                    integration="harbor",
                    method=method_upper,
                    path=path,
                    status=response.status_code,
                    latency_ms=round(latency_ms, 2),
                    attempt=attempt,
                )

                if response.status_code < 400:
                    log.debug("harbor.http.request.success")
                    return response

                log.warning(
                    "harbor.http.request.error",
                    error=response.text,
                )

                if (
                    self._should_retry(response.status_code)
                    and attempt < self.max_retries
                ):
                    backoff_seconds = self._get_backoff(
                        attempt, response.headers.get("Retry-After")
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue

                response.raise_for_status()

            except httpx.HTTPStatusError as exc:
                latency_ms = (perf_counter() - start) * 1000
                log = logger.bind(
                    integration="harbor",
                    method=method_upper,
                    path=path,
                    status=exc.response.status_code,
                    latency_ms=round(latency_ms, 2),
                    attempt=attempt,
                )
                log.error("harbor.http.request.exception", error=str(exc))

                if (
                    self._should_retry(exc.response.status_code)
                    and attempt < self.max_retries
                ):
                    backoff_seconds = self._get_backoff(
                        attempt, exc.response.headers.get("Retry-After")
                    )
                    await asyncio.sleep(backoff_seconds)
                    continue

                raise

            except httpx.RequestError as exc:
                latency_ms = (perf_counter() - start) * 1000
                log = logger.bind(
                    integration="harbor",
                    method=method_upper,
                    path=path,
                    status=None,
                    latency_ms=round(latency_ms, 2),
                    attempt=attempt,
                )
                log.error("harbor.http.request.transport_error", error=str(exc))

                if attempt < self.max_retries:
                    backoff_seconds = self._get_backoff(attempt, None)
                    await asyncio.sleep(backoff_seconds)
                    continue

                raise

    async def get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Response:
        return await self._request(
            "GET",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
        )

    def _extract_items(self, payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "items", "artifacts", "projects", "results"):
                if key in payload and isinstance(payload[key], list):
                    return payload[key]
        return []

    def _extract_total(self, response: Response, payload: Any) -> int | None:
        if (header := response.headers.get("X-Total-Count")) or (
            header := response.headers.get("x-total-count")
        ):
            try:
                return int(header)
            except (TypeError, ValueError):
                pass

        if isinstance(payload, dict):
            for key in ("total_count", "total", "count"):
                value = payload.get(key)
                if isinstance(value, int):
                    return value
        return None

    @cache_iterator_result()
    async def iter_pages(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        page: int = 1,
        page_size: int = 100,
        max_pages: int | None = None,
        timeout: float | None = None,
    ) -> AsyncGenerator[list[Any], None]:
        current_page = page
        fetched_pages = 0
        total_records: int | None = None

        while True:
            base_params = dict(params or {})
            request_params = {
                **base_params,
                "page": current_page,
                "page_size": page_size,
            }
            response = await self.get(
                path,
                params=request_params,
                headers=headers,
                timeout=timeout,
            )
            payload = response.json()
            items = self._extract_items(payload)

            page_log = logger.bind(
                integration="harbor",
                method="GET",
                path=path,
                page=current_page,
                page_size=page_size,
                item_count=len(items),
            )
            page_log.debug("harbor.pagination.page")

            if not items:
                break

            yield items

            fetched_pages += 1
            total_records = total_records or self._extract_total(response, payload)

            if len(items) < page_size:
                break

            if total_records is not None and current_page * page_size >= total_records:
                break

            if max_pages is not None and fetched_pages >= max_pages:
                break

            current_page += 1

    async def post(
        self,
        path: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> Response:
        return await self._request(
            "POST",
            path,
            json=json,
            params=params,
            headers=headers,
            timeout=timeout,
        )
