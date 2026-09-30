from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import THREAD_UPSERT_EVENTS
from plain.utils import ObjectKind
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import event_payload, thread_id_from_payload


class ThreadWebhookProcessor(PlainAbstractWebhookProcessor):
    def get_event_types(self) -> set[str]:
        return set(THREAD_UPSERT_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.THREAD]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        thread_id = thread_id_from_payload(body)
        if not thread_id:
            logger.warning("Plain thread webhook missing thread id; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        thread = await client.get_thread(thread_id)
        exclude_done = bool(
            getattr(resource_config.selector, "exclude_done_threads", False)
        )
        if exclude_done and thread.get("status") == "DONE":
            logger.info(
                "Plain thread {} is DONE and excludeDoneThreads is set; deleting",
                thread_id,
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[thread],
            )

        logger.info("Upserting Plain thread {}", thread_id)
        return WebhookEventRawResults(
            updated_raw_results=[thread],
            deleted_raw_results=[],
        )
