from typing import Any, Optional

from loguru import logger

from gitlab_integration.utils import ObjectKind
from gitlab_integration.events.hooks.base import GroupHandler
from port_ocean.context.ocean import ocean
from gitlab.v4.objects import Group


class Groups(GroupHandler):
    events = ["Subgroup Hook"]
    system_events = ["group_destroy", "group_create", "group_rename"]

    async def _on_hook(
        self, body: dict[str, Any], gitlab_group: Optional[Group]
    ) -> None:

        group_id = body.get("group_id")
        group_full_path = body.get("full_path")
        event_name = body["event_name"]

        logger.info(
            f"Handling event '{event_name}' for group with ID '{group_id}' and full path '{group_full_path}'"
        )
        if gitlab_group:
            await self._register_group(
                ObjectKind.GROUP,
                gitlab_group.asdict(),
            )
            await self._register_object_with_members(
                ObjectKind.GROUPWITHMEMBERS, gitlab_group
            )
            logger.info(f"Registered group {group_id}")
        elif (
            group_full_path
            and self.gitlab_service.should_run_for_path(group_full_path)
            and event_name in ("subgroup_destroy", "group_destroy")
        ):
            await ocean.unregister_raw(ObjectKind.GROUP, [body])
            await ocean.unregister_raw(ObjectKind.GROUPWITHMEMBERS, [body])
            logger.info(f"Unregistered group {group_id}")
            return

        else:
            logger.info(
                f"Group {group_id} was filtered for event {event_name}. Skipping..."
            )
