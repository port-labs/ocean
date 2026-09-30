from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import DISCUSSION_MESSAGE_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import (
    discussion_id_from_payload,
    discussion_message_id,
    discussion_thread_id,
    event_payload,
)


class DiscussionMessageWebhookProcessor(PlainAbstractWebhookProcessor):
    def get_event_types(self) -> set[str]:
        return set(DISCUSSION_MESSAGE_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DISCUSSION_MESSAGE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        discussion_id = discussion_id_from_payload(body)
        message_id = discussion_message_id(body)
        if not discussion_id or not message_id:
            logger.warning(
                "Plain discussion-message webhook missing discussion/message id; skipping"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        message = await client.get_discussion_message(
            discussion_id,
            message_id,
            discussion_thread_id(body),
        )
        logger.info("Upserting Plain discussion message {}", message_id)
        return WebhookEventRawResults(
            updated_raw_results=[message],
            deleted_raw_results=[],
        )
