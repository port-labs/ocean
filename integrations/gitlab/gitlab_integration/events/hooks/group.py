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
        logger.info(f"Handling {body['event_name']} for group {body['group_id']}")
        if gitlab_group:
            await self._register_group(gitlab_group)
        elif body["event_name"] in ("subgroup_destroy", "group_destroy"):
            await ocean.unregister_raw(ObjectKind.GROUP, [body])
        else:
            logger.warning(f"Group {body['group_id']} was filtered. Skipping ...")
