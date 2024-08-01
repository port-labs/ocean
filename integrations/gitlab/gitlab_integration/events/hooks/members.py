import typing
from typing import Any
from loguru import logger

from gitlab_integration.events.hooks.base import HookHandler
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean
from gitlab_integration.events.hooks.base import GroupHandler
from gitlab_integration.git_integration import MembersSelector
from port_ocean.context.event import event
from gitlab.v4.objects import Group, GroupMember
from gitlab_integration.git_integration import GitlabPortAppConfig


class Members(GroupHandler):
    events = ["Member Hook"]
    system_events = [
        "user_remove_from_group",
        "user_update_for_group",
        "user_add_to_group",
    ]

    async def _on_hook(self, body: dict[str, Any], gitlab_group: Group) -> None:

        event_name, user_username = body["event_name"], body["user_username"]
        logger.info(f"Handling {event_name} for group member {user_username}")

        if event_name == "user_remove_from_group":
            body['username'] = body['user_username']
            await ocean.unregister_raw(ObjectKind.MEMBER, [body])
        
        elif group_member := await self.gitlab_service.get_group_member(
            gitlab_group, body["user_id"]
        ):
            await self._register_group_member(group_member)
        
        else:
            logger.warning(
                f"Group Member {user_username} was filtered. Skipping ..."
            )

    async def _register_group_member(
        self,  group_member: GroupMember
    ) -> None:

        resource_configs=typing.cast(
            GitlabPortAppConfig, event.port_app_config
        ).resources

        matching_resource_configs = [
            resource_config
            for resource_config in resource_configs
            if (
                resource_config.kind == ObjectKind.MEMBER
                and isinstance(resource_config.selector, MembersSelector)
            )
        ]
        if not matching_resource_configs:
            logger.info(
                "Member resource not found in port app config, update port app config to include the resource type"
            )
            return
        for resource_config in matching_resource_configs:
            enrich_with_public_email = resource_config.selector.enrich_with_public_email
            if enrich_with_public_email:
                group_member = await self.gitlab_service.enrich_member_with_public_email(
                    group_member
                )
            else:
                group_member = group_member.asdict()
  
            await ocean.register_raw(ObjectKind.MEMBER, [group_member])
