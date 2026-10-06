from __future__ import annotations

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from plain.client import PlainClient
from plain.constants import DISCUSSION_EVENTS
from plain.utils import ObjectKind, is_ai_discussion
from webhook_processors.plain_abstract_webhook_processor import (
    PlainAbstractWebhookProcessor,
)
from webhook_processors.utils import (
    discussion_id_from_payload,
    event_payload,
    is_excluded_done_thread,
)


class DiscussionWebhookProcessor(PlainAbstractWebhookProcessor):
    def get_event_types(self) -> set[str]:
        return set(DISCUSSION_EVENTS)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DISCUSSION]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        body = event_payload(payload)
        discussion_id = discussion_id_from_payload(body)
        if not discussion_id:
            logger.warning("Plain discussion webhook missing id; skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = PlainClient()
        discussion = await client.get_discussion(discussion_id)
        exclude_ai = bool(
            getattr(resource_config.selector, "exclude_ai_discussions", False)
        )
        if exclude_ai and is_ai_discussion(discussion):
            logger.info(
                "Plain discussion {} is an AI/agent session and "
                "excludeAiDiscussions is set; deleting",
                discussion_id,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[discussion]
            )

        thread_id = discussion.get("threadId")
        if await is_excluded_done_thread(
            client,
            resource_config,
            thread_id if isinstance(thread_id, str) else None,
        ):
            logger.info(
                "Plain discussion {} belongs to a DONE thread and "
                "excludeDoneThreads is set; deleting",
                discussion_id,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[discussion]
            )

        logger.info("Upserting Plain discussion {}", discussion_id)
        return WebhookEventRawResults(
            updated_raw_results=[discussion],
            deleted_raw_results=[],
        )
