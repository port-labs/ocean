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

    async def validate_payload(self, payload: EventPayload) -> bool:
        # override the base class's validate_payload method
        return not ({"group_id", "user_id", "event_name"} - payload.keys())

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MEMBER, ObjectKind.GROUP_WITH_MEMBERS]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        group_id = payload["group_id"]
        event_name = payload["event_name"]
        user_name = payload["user_username"]
        user_id = payload["user_id"]

        logger.info(
            f"Handling webhook event '{event_name}' for group member '{user_name}'"
        )

        if event_name == "user_remove_from_group":
            logger.info(
                f"Removing member '{user_name}' from group '{group_id}' due to event '{event_name}'"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[payload]
            )

        selector: GitlabMemberSelector = typing.cast(
            GitlabMemberSelector, resource_config.selector
        )

        if not selector.include_bot_members and "bot" in user_name.lower():
            logger.info(
                f"Excluding bot member '{user_name}' from group '{group_id}' because include_bot_members is false"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[payload]
            )

        group_member = await self._gitlab_webhook_client.get_group_member(
            group_id, user_id
        )

        if not group_member:  # 404 not found
            logger.warning(
                f"Group member '{user_name}' not found in group '{group_id}'"
            )
            group_member = {}

        return WebhookEventRawResults(
            updated_raw_results=[group_member], deleted_raw_results=[]
        )
