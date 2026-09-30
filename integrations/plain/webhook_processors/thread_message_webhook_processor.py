from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import THREAD_MESSAGE_EVENTS
from plain.exceptions import PlainGraphQLError
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import (
    event_payload,
    is_timeline_removed,
    timeline_entry_refs,
)


class ThreadMessageWebhookProcessor(PlainAbstractWebhookProcessor):
    def get_event_types(self) -> set[str]:
        return set(THREAD_MESSAGE_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.THREAD_MESSAGE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        customer_id, entry_id = timeline_entry_refs(body)
        if is_timeline_removed(body):
            if not entry_id:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )
            logger.info("Deleting Plain thread message {}", entry_id)
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": entry_id}],
            )

        if not customer_id or not entry_id:
            logger.warning(
                "Plain thread-message webhook missing customer/timeline ids; skipping"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        try:
            entry = await client.get_timeline_entry(customer_id, entry_id)
        except PlainGraphQLError as error:
            if "has no message text" in str(error):
                logger.info(
                    "Ignoring Plain timeline entry {} without message text", entry_id
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )
            raise

        logger.info("Upserting Plain thread message {}", entry_id)
        return WebhookEventRawResults(
            updated_raw_results=[entry],
            deleted_raw_results=[],
        )
