from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.helpers.webhook_scope import (
    dashboard_webhook_endpoints_url,
)

_WEBHOOK_NAME = "Port Ocean Azure AI Foundry"
_RESPONSE_WEBHOOK_EVENTS = [
    "response.completed",
    "response.failed",
    "response.cancelled",
    "response.incomplete",
]

# account host -> signing secret captured at webhook create time
_signing_secrets: dict[str, str] = {}


def get_signing_secret_for_host(account_host: str) -> str | None:
    return _signing_secrets.get(account_host)


def has_any_signing_secret() -> bool:
    return bool(_signing_secrets)


def clear_webhook_secret_cache() -> None:
    _signing_secrets.clear()


class FoundryWebhookClient:
    def __init__(
        self,
        *,
        http: OceanAsyncClient,
        authenticator: object,
        account_base_url: str,
        verify_secrets: bool = True,
    ) -> None:
        self._http = http
        self._authenticator = authenticator
        self._account_base_url = account_base_url.rstrip("/")
        self._verify_secrets = verify_secrets
        host = self._account_base_url.removeprefix("https://").removeprefix("http://")
        self._account_host = host.split("/")[0]

    @property
    def verify_webhook_secrets(self) -> bool:
        return self._verify_secrets and bool(self.signing_secret)

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self.signing_secret)

    @property
    def signing_secret(self) -> str | None:
        return _signing_secrets.get(self._account_host)

    async def _auth_headers(self) -> dict[str, str]:
        return await self._authenticator.get_authorization_header()

    async def list_webhook_endpoints(self) -> list[dict[str, Any]]:
        url = dashboard_webhook_endpoints_url(self._account_base_url)
        headers = await self._auth_headers()
        response = await self._http.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    async def create_webhook_endpoint(
        self, *, webhook_url: str, event_types: list[str]
    ) -> dict[str, Any]:
        url = dashboard_webhook_endpoints_url(self._account_base_url)
        headers = await self._auth_headers()
        response = await self._http.post(
            url,
            headers=headers,
            json={
                "name": _WEBHOOK_NAME,
                "url": webhook_url,
                "event_types": event_types,
            },
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise httpx.HTTPError("Unexpected create webhook response")
        return body

    async def upsert_webhook(self, base_url: str) -> None:
        webhook_url = f"{base_url.rstrip('/')}/integration/webhook"
        try:
            existing = next(
                (
                    item
                    for item in await self.list_webhook_endpoints()
                    if item.get("url") == webhook_url
                ),
                None,
            )
            if existing is not None:
                current = set(existing.get("event_types") or [])
                if set(_RESPONSE_WEBHOOK_EVENTS).issubset(current):
                    if not self.signing_secret:
                        logger.warning(
                            f"Foundry webhook already registered for {self._account_host} "
                            "but signing secret is unknown in this process; "
                            "signature verification disabled until recreated"
                        )
                    else:
                        logger.info(
                            f"Foundry webhook already registered for {webhook_url}"
                        )
                    return
                logger.warning(
                    "Foundry webhook URL exists but event_types differ; "
                    "update manually in Foundry dashboard"
                )
                return

            created = await self.create_webhook_endpoint(
                webhook_url=webhook_url,
                event_types=_RESPONSE_WEBHOOK_EVENTS,
            )
            secret = created.get("signing_secret") or created.get("secret")
            if isinstance(secret, str) and secret:
                _signing_secrets[self._account_host] = secret
                logger.info(
                    f"Created Foundry webhook for {self._account_host}; "
                    "signing secret cached in-process"
                )
            logger.info(f"Registered Foundry webhook for {webhook_url}")
        except httpx.HTTPError as error:
            logger.error(
                f"Failed to register Foundry webhook for {self._account_host}: {error}"
            )
