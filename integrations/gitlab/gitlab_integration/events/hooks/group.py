from typing import Any

from loguru import logger

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


class GroupHook(HookHandler):
    events = ["Subgroup Hook"]
    system_events = [
        "group_destroy",
        "group_create",
        "group_rename",
    ]

    async def on_hook(self, event: str, body: dict[str, Any]) -> None:
        event_name = body["event_name"]

        logger.info(f"Handling {event_name} for {event}")

        group_id = body["group_id"] if "group_id" in body else body["group"]["id"]

        logger.info(f"Handling hook {event} for group {group_id}")

        group = await self.gitlab_service.get_group(group_id)

        group_full_path = body.get("full_path")
        if group:
            await ocean.register_raw(ObjectKind.GROUP, [group.asdict()])
        elif (
            group_full_path
            and self.gitlab_service.should_run_for_path(group_full_path)
            and event_name in ("subgroup_destroy", "group_destroy")
        ):
            await ocean.unregister_raw(ObjectKind.GROUP, [body])
        else:
            logger.info(f"Group {group_id} was filtered for event {event}. Skipping...")
