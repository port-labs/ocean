from __future__ import annotations

from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.auth.factory import create_authenticator
from helpers.project_scope import get_project_endpoint
from helpers.webhook_scope import (
    account_base_url_from_project_endpoint,
    dashboard_webhook_endpoints_url,
)

_WEBHOOK_NAME = "Port Ocean Azure AI Foundry"
_RESPONSE_WEBHOOK_EVENTS = [
    "response.completed",
    "response.failed",
    "response.cancelled",
    "response.incomplete",
]


class FoundryWebhookClient:
    def __init__(
        self,
        *,
        http: OceanAsyncClient,
        signing_secret: str | None,
        verify_secrets: bool,
        authenticator: object,
    ) -> None:
        self._http = http
        self._signing_secret = signing_secret
        self._verify_secrets = verify_secrets
        self._authenticator = authenticator

    @property
    def verify_webhook_secrets(self) -> bool:
        return self._verify_secrets

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._signing_secret)

    @property
    def signing_secret(self) -> str | None:
        return self._signing_secret

    async def _auth_headers(self) -> dict[str, str]:
        return await self._authenticator.get_authorization_header()

    async def list_webhook_endpoints(self) -> list[dict[str, Any]]:
        url = dashboard_webhook_endpoints_url(
            account_base_url_from_project_endpoint(get_project_endpoint())
        )
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
        url = dashboard_webhook_endpoints_url(
            account_base_url_from_project_endpoint(get_project_endpoint())
        )
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
                    logger.info(f"Foundry webhook already registered for {webhook_url}")
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
                self._signing_secret = secret
                logger.info(
                    "Created Foundry webhook endpoint; store webhookSigningSecret "
                    "in integration config for verification across restarts"
                )
            logger.info(f"Registered Foundry webhook for {webhook_url}")
        except httpx.HTTPError as error:
            logger.error(f"Failed to register Foundry webhook endpoints: {error}")
