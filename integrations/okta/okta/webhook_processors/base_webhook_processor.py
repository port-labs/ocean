from abc import abstractmethod

from fastapi import Request
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class OktaBaseWebhookProcessor(AbstractWebhookProcessor):

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _verify_webhook_signature(self, request: Request) -> bool:
        """
        Validate the authenticity of the webhook payload using the Authorization header.
        If no secret is configured, validation is bypassed.
        """
        secret = ocean.integration_config.get("webhook_secret")

        if not secret:
            logger.info(
                "No secret configured for Okta incoming webhooks; accepting event without signature validation."
            )
            return True

        provided = request.headers.get("authorization", "")
        if not provided:
            logger.error(
                "Missing 'authorization' header. Webhook authentication failed."
            )
            return False

        return provided == secret

    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool: ...

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not (event._original_request and await self._should_process_event(event)):
            return False
        return await self._verify_webhook_signature(event._original_request)

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Basic validation: ensure payload has data.events list."""
        if not isinstance(payload, dict):
            return False

        events = payload["data"]["events"]
        if not isinstance(events, list):
            return False

        for event_object in events:
            if not isinstance(event_object, dict):
                return False

            event_type = event_object["eventType"]
            targets = event_object["target"]

            if not isinstance(event_type, str) or not event_type:
                return False
            if not isinstance(targets, list):
                return False

            for target in targets:
                if not isinstance(target, dict):
                    return False
                _type = target["type"]
                _id = target["id"]
                if not isinstance(_type, str) or not _type:
                    return False
                if _id is None:
                    return False

        return True
