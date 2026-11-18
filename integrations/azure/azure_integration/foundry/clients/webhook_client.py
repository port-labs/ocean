from __future__ import annotations

from typing import Any

import httpx
from azure.identity.aio import DefaultAzureCredential
from loguru import logger
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.helpers.webhook_scope import (
    dashboard_webhook_endpoints_url,
)

_WEBHOOK_NAME = "Port Ocean Azure AI Foundry"
_FOUNDRY_SCOPE = "https://ai.azure.com/.default"
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
        account_base_url: str,
    ) -> None:
        self._http = http
        self._account_base_url = account_base_url.rstrip("/")
        host = self._account_base_url.removeprefix("https://").removeprefix("http://")
        self._account_host = host.split("/")[0]
        self._credential: DefaultAzureCredential | None = None

    async def _auth_headers(self) -> dict[str, str]:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def list_webhook_endpoints(self) -> list[dict[str, Any]]:
        url = dashboard_webhook_endpoints_url(self._account_base_url)
        headers = await self._auth_headers()
        response = await self._http.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
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
                    logger.info(f"Foundry webhook already registered for {webhook_url}")
                    return
                logger.warning(
                    "Foundry webhook URL exists but event_types differ; "
                    "update manually in Foundry dashboard"
                )
                return

            await self.create_webhook_endpoint(
                webhook_url=webhook_url,
                event_types=_RESPONSE_WEBHOOK_EVENTS,
            )
            logger.info(f"Registered Foundry webhook for {webhook_url}")
        except httpx.HTTPError as error:
            logger.error(
                f"Failed to register Foundry webhook for {self._account_host}: {error}"
            )
