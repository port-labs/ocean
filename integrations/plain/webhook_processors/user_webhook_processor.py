from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import USER_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import assignee_user_id, event_payload


class UserWebhookProcessor(PlainAbstractWebhookProcessor):
    """Plain has no user.* webhooks; refresh users from assignment transitions."""

    def get_event_types(self) -> set[str]:
        return set(USER_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        user_id = assignee_user_id(body)
        if not user_id:
            logger.info(
                "Plain assignment webhook has no human user assignee; skipping user sync"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        user = await client.get_user(user_id)
        logger.info("Upserting Plain user {}", user_id)
        return WebhookEventRawResults(
            updated_raw_results=[user],
            deleted_raw_results=[],
        )
