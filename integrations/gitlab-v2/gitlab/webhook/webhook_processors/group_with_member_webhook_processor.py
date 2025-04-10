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


class GroupWithMemberWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = [
        "group_create",
        "group_destroy",
        "subgroup_create",
        "subgroup_destroy",
        "user_add_to_group",
        "user_remove_from_group",
        "user_update_for_group",
    ]
    hooks = ["Subgroup Hook", "Member Hook"]

    async def validate_payload(self, payload: EventPayload) -> bool:
        # override the base class's validate_payload method
        return not ({"group_id", "event_name"} - payload.keys())

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.GROUP_WITH_MEMBERS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        group_id = payload["group_id"]
        event_name = payload["event_name"]

        logger.info(
            f"Handling {event_name} webhook event for group with ID '{group_id}''"
        )

        # For destroy events, no need to fetch group since it's already deleted
        if event_name in ("subgroup_destroy", "group_destroy"):
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload],
            )

        selector = typing.cast(GitlabMemberSelector, resource_config.selector)
        include_bot_members = bool(selector.include_bot_members)

        group = await self._gitlab_webhook_client.get_group(group_id)
        if group:
            group = await self._gitlab_webhook_client.enrich_group_with_members(
                group, include_bot_members=include_bot_members
            )
        else:
            logger.warning(f"Group with ID '{group_id}' not found")
            group = {}

        return WebhookEventRawResults(
            updated_raw_results=[group],
            deleted_raw_results=[],
        )
