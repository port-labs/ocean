from __future__ import annotations

from typing import Any

import httpx
from azure.identity.aio import DefaultAzureCredential
from loguru import logger
from port_ocean.helpers.async_client import OceanAsyncClient

from azure_integration.foundry.models.responses import TERMINAL_EVENTS

_WEBHOOK_NAME = "Port Ocean Azure AI Foundry"
_FOUNDRY_SCOPE = "https://ai.azure.com/.default"
_RESPONSE_WEBHOOK_EVENTS = list(TERMINAL_EVENTS)


class FoundryWebhookClient:
    def __init__(self, *, account_base_url: str) -> None:
        self._http = OceanAsyncClient(timeout=httpx.Timeout(60.0))
        self._account_base_url = account_base_url.rstrip("/")
        host = self._account_base_url.removeprefix("https://").removeprefix("http://")
        self._account_host = host.split("/")[0]
        self._credential: DefaultAzureCredential | None = None
        self._endpoints_url = (
            f"{self._account_base_url}/openai/v1/dashboard/webhook_endpoints"
        )

    async def __aenter__(self) -> FoundryWebhookClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()
        if self._credential is not None:
            await self._credential.close()
            self._credential = None

    async def _auth_headers(self) -> dict[str, str]:
        if self._credential is None:
            self._credential = DefaultAzureCredential()
        token = await self._credential.get_token(_FOUNDRY_SCOPE)
        return {"Authorization": f"Bearer {token.token}"}

    async def list_webhook_endpoints(self) -> list[dict[str, Any]]:
        headers = await self._auth_headers()
        response = await self._http.get(self._endpoints_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    async def create_webhook_endpoint(
        self, *, webhook_url: str, event_types: list[str]
    ) -> dict[str, Any]:
        headers = await self._auth_headers()
        response = await self._http.post(
            self._endpoints_url,
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

    async def update_webhook_endpoint(
        self, endpoint_id: str, *, event_types: list[str]
    ) -> None:
        url = f"{self._endpoints_url}/{endpoint_id}"
        headers = await self._auth_headers()
        response = await self._http.post(
            url,
            headers=headers,
            json={"event_types": event_types},
        )
        response.raise_for_status()

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
                endpoint_id = existing.get("id")
                if not endpoint_id:
                    logger.warning(
                        "Foundry webhook URL exists but event_types differ and "
                        "endpoint id is missing; update manually in Foundry dashboard"
                    )
                    return
                await self.update_webhook_endpoint(
                    str(endpoint_id),
                    event_types=_RESPONSE_WEBHOOK_EVENTS,
                )
                logger.info(f"Updated Foundry webhook events for {webhook_url}")
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
