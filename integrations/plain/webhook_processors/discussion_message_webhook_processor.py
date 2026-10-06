from __future__ import annotations

from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import DISCUSSION_MESSAGE_EVENTS
from plain.utils import ObjectKind, is_ai_discussion
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import (
    discussion_id_from_payload,
    discussion_message_id,
    discussion_thread_id,
    event_payload,
    is_excluded_done_thread,
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
        thread_id = discussion_thread_id(body)
        exclude_ai = bool(
            getattr(resource_config.selector, "exclude_ai_discussions", False)
        )
        exclude_done = bool(
            getattr(resource_config.selector, "exclude_done_threads", False)
        )
        if exclude_ai or (exclude_done and not thread_id):
            discussion: dict[str, Any] = await client.get_discussion(discussion_id)
            if exclude_ai and is_ai_discussion(discussion):
                logger.info(
                    "Plain discussion message {} belongs to an AI/agent session "
                    "and excludeAiDiscussions is set; deleting",
                    message_id,
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[{"id": message_id}],
                )
            if not thread_id:
                raw_thread_id = discussion.get("threadId")
                if isinstance(raw_thread_id, str) and raw_thread_id:
                    thread_id = raw_thread_id

        if await is_excluded_done_thread(client, resource_config, thread_id):
            logger.info(
                "Plain discussion message {} belongs to a DONE thread and "
                "excludeDoneThreads is set; deleting",
                message_id,
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": message_id}],
            )

        message = await client.get_discussion_message(
            discussion_id,
            message_id,
            thread_id,
        )
        logger.info("Upserting Plain discussion message {}", message_id)
        return WebhookEventRawResults(
            updated_raw_results=[message],
            deleted_raw_results=[],
        )
