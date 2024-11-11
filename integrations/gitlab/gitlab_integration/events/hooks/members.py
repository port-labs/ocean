from typing import Any, Optional
from loguru import logger

from gitlab_integration.utils import ObjectKind
from gitlab_integration.events.hooks.base import GroupHandler
from gitlab.v4.objects import Group


class Members(GroupHandler):
    events = ["Member Hook"]
    system_events = [
        "user_remove_from_group",
        "user_update_for_group",
        "user_add_to_group",
    ]

    async def _on_hook(
        self, body: dict[str, Any], gitlab_group: Optional[Group]
    ) -> None:
        if gitlab_group:
            event_name, user_username = (body["event_name"], body["user_username"])
            logger.info(f"Handling {event_name} for group member {user_username}")
            await self._register_object_with_members(
                ObjectKind.GROUPWITHMEMBERS, gitlab_group
            )
        else:
            logger.info(
                f"Group member's group {body['group_id']} was filtered for event {body['event_name']}. Skipping..."
            )
