from loguru import logger
from typing import Any
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from kinds import Kinds
from jira_server.webhook_processors.events import JiraUserEvents, JiraDeletedUserEvent
from jira_server.webhook_processors.processors._base_webhook_processor import (
    _BaseJiraWebhookProcessor,
)
from initialize_client import init_webhook_client


class UserWebhookProcessor(_BaseJiraWebhookProcessor):

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.USER]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("webhookEvent")
        return event_type in JiraUserEvents

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "webhookEvent" in payload and "user" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        user = payload["user"]
        event_type = payload["webhookEvent"]
        logger.info(
            f"Processing user webhook event: {event_type} for user {user['name']}"
        )

        updated_raw_results: list[dict[str, Any]] = []
        deleted_raw_results: list[dict[str, Any]] = []
        if event_type == JiraDeletedUserEvent:
            deleted_raw_results.append(user)
        else:
            client = init_webhook_client()
            user_info = await client.get_single_user(user["key"])
            if user_info:
                updated_raw_results.append(user_info)
            else:
                logger.error(f"User {user['name']} not found in Jira")

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
