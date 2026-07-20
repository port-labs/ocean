from __future__ import annotations

import asyncio
from typing import Any, cast

import httpx
from loguru import logger
from werkzeug.local import LocalProxy, LocalStack

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.helpers.async_client import OceanAsyncClient
from port_ocean.helpers.retry import RetryConfig

_lifecycle_http_client: LocalStack["OceanResyncHttpClient"] = LocalStack()


def _truncate(text: str, max_len: int = 256) -> str:
    return text if len(text) <= max_len else text[:max_len] + "…"


class OceanResyncHttpClient(OceanAsyncClient):
    """Best-effort authenticated HTTP client. Never raises; logs errors and swallows."""

    def __init__(self, auth: PortAuthentication, timeout: int = 10) -> None:
        self._lifecycle_auth = auth
        super().__init__(
            timeout=timeout,
            retry_config=RetryConfig(
                retryable_methods=[
                    "POST",
                    "HEAD",
                    "GET",
                    "PUT",
                    "DELETE",
                    "OPTIONS",
                    "TRACE",
                ]
            ),
        )

    async def _raw_post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await super().post(url, **kwargs)

    async def _raw_get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await super().get(url, **kwargs)

    async def do_post(self, url: str, json: dict[str, Any] | None = None) -> None:
        try:
            headers = await self._lifecycle_auth.headers()
            response = await self._raw_post(url, headers=headers, json=json)

            if response.is_error:
                escaped = response.text.replace("{", "{{").replace("}", "}}")
                logger.warning(
                    f"API returned an error for POST {url}: {_truncate(escaped)}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
            else:
                logger.info(
                    f"API request succeeded for POST {url}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Failed HTTP request: {type(exc).__name__}: {exc}")

    async def do_get(self, url: str) -> dict[str, Any] | None:
        try:
            headers = await self._lifecycle_auth.headers()
            response = await self._raw_get(url, headers=headers)
            if response.is_error:
                escaped = response.text.replace("{", "{{").replace("}", "}}")
                logger.warning(
                    f"API returned an error for GET {url}: {_truncate(escaped)}",
                    status_code=response.status_code,
                    response_body=_truncate(response.text),
                )
                return None
            logger.info(
                f"API request succeeded for GET {url}",
                status_code=response.status_code,
                response_body=_truncate(response.text),
            )
            return response.json()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Failed HTTP request: {type(exc).__name__}: {exc}")
            return None


def _get_lifecycle_http_client_context(
    auth: PortAuthentication,
) -> OceanResyncHttpClient:
    client = _lifecycle_http_client.top
    if client is None:
        client = OceanResyncHttpClient(auth=auth)
        _lifecycle_http_client.push(client)
    return client


def get_lifecycle_http_client(auth: PortAuthentication) -> OceanResyncHttpClient:
    return cast(
        OceanResyncHttpClient,
        LocalProxy(lambda: _get_lifecycle_http_client_context(auth)),
    )
