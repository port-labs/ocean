from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from anthropic.types.beta import UnwrapWebhookEvent
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient

from clients.exceptions import WebhookSigningSecretNotConfiguredError

# Platform Console admin API (not covered by the Anthropic SDK webhooks resource).
_WEBHOOKS_BETA = "webhooks-2026-03-01"
_WEBHOOK_NAME = "Port Ocean Integration"
_WEBHOOK_EVENTS = [
    "session.status_run_started",
    "session.status_idled",
    "session.status_rescheduled",
    "session.status_terminated",
    "session.deleted",
    "session.updated",
    "vault.created",
    "vault.archived",
    "vault.deleted",
]
_WEBHOOK_SIGNING_SECRET_SPEC_KEY = "webhookSigningSecret"


class ClaudeWebhookClient:
    def __init__(
        self,
        http_client: OceanAsyncClient,
        anthropic_client: AsyncAnthropic,
        console_host: str,
        api_key: str,
        webhook_signing_secret: str | None = None,
        verify_webhook_secrets: bool = False,
        anthropic_version: str | None = None,
    ) -> None:
        self._http = http_client
        self._anthropic = anthropic_client
        self._console_host = console_host.rstrip("/")
        self._api_key = api_key
        self._webhook_signing_secret = webhook_signing_secret
        self._verify_webhook_secrets = verify_webhook_secrets
        self._anthropic_version = anthropic_version

    @property
    def verify_webhook_secrets(self) -> bool:
        return self._verify_webhook_secrets

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._webhook_signing_secret)

    def unwrap_webhook(
        self, payload: str, headers: Mapping[str, str]
    ) -> UnwrapWebhookEvent:
        if not self._webhook_signing_secret:
            raise WebhookSigningSecretNotConfiguredError(
                "Webhook signing secret is not configured"
            )
        return self._anthropic.beta.webhooks.unwrap(
            payload, headers=headers, key=self._webhook_signing_secret
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-beta": _WEBHOOKS_BETA,
            "content-type": "application/json",
        }
        if self._anthropic_version:
            headers["anthropic-version"] = self._anthropic_version
        return headers

    def _signing_secret_name(self) -> str:
        identifier = ocean.config.integration.identifier.replace("/", "-")
        return f"{identifier}-claude-webhook-signing-secret"

    async def _persist_signing_secret(self, signing_secret: str) -> None:
        """Store the Claude signing secret as an org secret and point SaaS spec at it."""
        secret_name = self._signing_secret_name()
        description = (
            "Claude Managed Agents webhook signing secret for Port Ocean live events"
        )
        try:
            await ocean.port_client.create_organization_secret(
                secret_name=secret_name,
                secret_value=signing_secret,
                description=description,
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in (409, 422):
                raise
            await ocean.port_client.update_organization_secret(
                secret_name=secret_name,
                secret_value=signing_secret,
                description=description,
            )

        await ocean.port_client.patch_integration(
            spec={
                "integrationSpec": {
                    _WEBHOOK_SIGNING_SECRET_SPEC_KEY: secret_name,
                }
            }
        )
        self._webhook_signing_secret = signing_secret
        logger.info(
            f"Persisted Claude webhook signing secret as org secret '{secret_name}' "
            "and patched integrationSpec"
        )

    async def get_webhook_by_url(self, webhook_url: str) -> dict[str, Any] | None:
        response = await self._http.get(
            f"{self._console_host}/v1/webhooks", headers=self._headers()
        )
        response.raise_for_status()
        return next(
            (
                webhook
                for webhook in response.json().get("data") or []
                if webhook.get("url") == webhook_url
            ),
            None,
        )

    async def update_webhook_events(
        self, webhook_id: str, enabled_events: list[str]
    ) -> None:
        response = await self._http.post(
            f"{self._console_host}/v1/webhooks/{webhook_id}",
            headers=self._headers(),
            json={"enabled_events": enabled_events},
        )
        response.raise_for_status()

    async def upsert_webhook(self, base_url: str) -> None:
        """Register the webhook URL; on 409, ensure required events are covered."""
        webhook_url = f"{base_url.rstrip('/')}/integration/webhook"
        headers = self._headers()

        try:
            response = await self._http.post(
                f"{self._console_host}/v1/webhooks",
                headers=headers,
                json={
                    "url": webhook_url,
                    "name": _WEBHOOK_NAME,
                    "description": "Port Ocean Claude Managed Agents live events",
                    "enabled_events": _WEBHOOK_EVENTS,
                },
            )
            if response.status_code == 409:
                existing = await self.get_webhook_by_url(webhook_url)
                if not existing:
                    logger.warning(
                        f"Claude webhook 409 for {webhook_url} but none found in list"
                    )
                    return
                current = set(existing.get("enabled_events") or [])
                if set(_WEBHOOK_EVENTS).issubset(current):
                    logger.info(f"Claude webhook already exists for {webhook_url}")
                    return
                await self.update_webhook_events(
                    existing["id"],
                    sorted(current | set(_WEBHOOK_EVENTS)),
                )
                logger.info(
                    f"Updated Claude webhook {existing['id']} events for {webhook_url}"
                )
                return

            if response.is_error:
                logger.error(
                    f"Failed to create Claude webhook for {webhook_url}: "
                    f"{response.status_code} {(response.text or '')[:500]}"
                )
                return

            created = response.json()
            logger.info(f"Created Claude webhook {created.get('id')} for {webhook_url}")
            await self._maybe_store_signing_secret(created.get("signing_secret"))
        except httpx.HTTPError as error:
            logger.error(f"Failed to ensure Claude webhook for {webhook_url}: {error}")

    async def _maybe_store_signing_secret(self, signing_secret: str | None) -> None:
        if not signing_secret or not self._verify_webhook_secrets:
            return
        if self._webhook_signing_secret:
            return

        self._webhook_signing_secret = signing_secret
        if not ocean.app.is_saas():
            logger.warning(
                "verifyWebhookSecrets is enabled but this is not a SaaS install; "
                "using the create-response signing secret in-memory only. See "
                "https://docs.port.io/agent-management/external-agents/claude-managed-agents/#webhook-configuration "
                "for how to persist webhookSigningSecret across restarts."
            )
            return

        try:
            await self._persist_signing_secret(signing_secret)
        except Exception as error:
            logger.error(
                f"Failed to persist Claude webhook signing secret to Port: {error}"
            )
