from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitlabMemberSelector
import typing


class MemberWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = [
        "user_remove_from_group",
        "user_update_for_group",
        "user_add_to_group",
    ]
    hooks = ["Member Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MEMBER, ObjectKind.GROUPWITHMEMBERS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        group_id = payload["group_id"]
        event_name = payload["event_name"]
        user_name = payload["user_username"]
        user_id = payload["user_id"]

        logger.info(
            f"Handling {event_name} webhook event for group member '{user_name}'"
        )

        # For remove events, no need to fetch member since it's already deleted
        if event_name in ("user_remove_from_group"):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload],
            )

        # Only fetch group, member if needed
        group_member = await self._gitlab_webhook_client.get_group_member(
            group_id, user_id
        )
        selector = typing.cast(GitlabMemberSelector, resource_config.selector)
        include_bot_members = bool(selector.include_bot_members)
        if not include_bot_members and "bot" in group_member["username"].lower():
            logger.info(
                f"Skipping bot member {group_member['username']} for group {group_id} because include_bot_members is false"
            )

        return WebhookEventRawResults(
            updated_raw_results=[group_member] if group_member else [],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        # override the base class's validate_payload method
        return not ({"group_id", "user_id", "event_name"} - payload.keys())
