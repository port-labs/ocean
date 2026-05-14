from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from aws.webhook.events import SNS_MESSAGE_TYPE_HEADER, SnsMessageType
from aws.webhook.processors.base import _get_sns_verifier


class SnsSubscriptionConfirmationProcessor(AbstractWebhookProcessor):
    """Handles `SubscriptionConfirmation` and `UnsubscribeConfirmation`.

    Confirmation requests don't touch the catalog but are
    security-sensitive: a forged confirmation could bind an attacker's
    topic to the endpoint. Same SNS signature verification applies
    here as for notifications.
    """

    async def authenticate(
        self, payload: EventPayload, headers: EventHeaders
    ) -> bool:
        return await _get_sns_verifier().verify(payload)

    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            isinstance(payload, dict)
            and payload.get("Type")
            in {
                SnsMessageType.SUBSCRIPTION_CONFIRMATION.value,
                SnsMessageType.UNSUBSCRIBE_CONFIRMATION.value,
            }
            and isinstance(payload.get("SubscribeURL"), str)
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get(SNS_MESSAGE_TYPE_HEADER) in {
            SnsMessageType.SUBSCRIPTION_CONFIRMATION.value,
            SnsMessageType.UNSUBSCRIBE_CONFIRMATION.value,
        }

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        subscribe_url = payload.get("SubscribeURL", "")
        topic_arn = payload.get("TopicArn", "")
        if not self._is_url_allowed(subscribe_url):
            logger.warning(
                "SNS confirmation rejected — SubscribeURL host not in allowlist",
                extra={
                    "subscribe_url_host": urlparse(subscribe_url).hostname,
                    "outcome": "rejected_subscribe_url",
                },
            )
            return WebhookEventRawResults([], [])

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(subscribe_url)
                response.raise_for_status()
        except Exception:
            logger.exception(
                "SNS confirmation: failed to GET SubscribeURL",
                extra={"topic_arn": topic_arn, "outcome": "error_confirm"},
            )
            raise

        logger.info(
            "SNS subscription confirmed",
            extra={"topic_arn": topic_arn, "outcome": "subscription_confirmed"},
        )
        return WebhookEventRawResults([], [])

    @staticmethod
    def _is_url_allowed(url: str) -> bool:
        # Share the host allowlist with the signature verifier so a
        # subscription confirmation can't escape rules a notification
        # would have to follow.
        verifier = _get_sns_verifier()
        return verifier._is_url_allowed(url)  # noqa: SLF001
