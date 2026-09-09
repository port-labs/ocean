from typing import cast

from webhook_processors.linear_abstract_webhook_processor import (
    _LinearAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from linear.client import LinearClient
from linear.core.exporters import UserExporter
from linear.core.exporters.user_exporter import GetUserOptions
from integration import UserResourceConfig
from linear.utils import ObjectKind
from loguru import logger


class UserWebhookProcessor(_LinearAbstractWebhookProcessor):
    """Processes user-related webhook events from Linear."""

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get(
            "linear-event"
        ) == "User" and await self.is_action_allowed(event.payload.get("action", ""))

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event_data = payload["data"]
        user_id = event_data["id"]
        action = payload["action"]

        logger.info(f"Processing webhook event for user with ID: {user_id}")

        if action == "remove":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[event_data],
            )

        client = LinearClient.create_from_ocean_configuration()
        user_exporter = UserExporter(client)
        options = GetUserOptions.from_resource_config(
            cast(UserResourceConfig, resource_config), resource_id=user_id
        )
        data_to_update = await user_exporter.get_resource(options)

        return WebhookEventRawResults(
            updated_raw_results=[data_to_update], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            isinstance(payload, dict)
            and all(key in payload for key in ("type", "data", "action"))
            and payload["type"] == "User"
            and "id" in payload["data"]
        )
