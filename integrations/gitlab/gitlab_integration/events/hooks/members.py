import typing
from typing import Any, List, Optional
from loguru import logger
import asyncio

from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean
from gitlab_integration.events.hooks.base import GroupHandler
from gitlab_integration.git_integration import MembersSelector
from port_ocean.context.event import event
from gitlab.v4.objects import Group, GroupMember
from gitlab_integration.git_integration import GitlabPortAppConfig
from gitlab_integration.events.utils import remove_prefix_from_keys

CONCURENT_TASKS_LIMIT = 10


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
        event_name, user_username = (body["event_name"], body["user_username"])
        logger.info(f"Handling {event_name} for group member {user_username}")

        if event_name == "user_remove_from_group":
            # This event is triggered by GitLab when a group or subgroup is destroyed.
            # When a group is deleted, GitLab tries to remove all direct members associated with that group.
            # However, to prevent accidental deletion of members who may also be part of other groups,
            # we perform a check to determine if the member is associated with any other groups.
            # If the member is not associated with any other groups, we proceed to delete the member from Port.
            # Otherwise, we skip the deletion process to ensure that members are not inadvertently removed
            # from groups they are still part of.
            if not (await self._is_root_group_member(body["user_id"])):
                body = remove_prefix_from_keys(
                    "user_", body
                )  # Removing user_ prefix from the keys makes the event data close to being consistent with the member api response data.
                # Thereby enhancing flexibility in processing custom identifiers.
                await ocean.unregister_raw(ObjectKind.MEMBER, [body])
            else:
                logger.warning(
                    f"Group member {user_username} belongs to other groups. Skipping ..."
                )

        elif gitlab_group:
            if group_member := await self.gitlab_service.get_group_member(
                gitlab_group, body["user_id"]
            ):
                await self._register_group_member(group_member)
                if body["event_name"] == "user_add_to_group":
                    # This step ensures that when a new user is added to a group, we update the group entities to link the newly created member to the group.
                    # Note: This event is triggered by Gitlab when a group or subgroup is created.
                    await self._register_group(gitlab_group)

        else:
            logger.warning(f"Group Member {user_username} was filtered. Skipping ...")

    async def _register_group_member(self, group_member: GroupMember) -> None:

        resource_configs = typing.cast(
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
            member = (
                await self.gitlab_service.enrich_member_with_public_email(group_member)
                if enrich_with_public_email
                else group_member.asdict()
            )

            await ocean.register_raw(ObjectKind.MEMBER, [member])

    async def _is_root_group_member(self, member_id: int) -> bool:
        root_groups: List[Group] = self.gitlab_service.get_root_groups()
        semaphore = asyncio.Semaphore(CONCURENT_TASKS_LIMIT)

        async def check_group(group: Group) -> bool:
            async with semaphore:
                return any(
                    [await self.gitlab_service.get_group_member(group, member_id)]
                )

        tasks = [asyncio.create_task(check_group(group)) for group in root_groups]
        for completed_task in asyncio.as_completed(tasks):
            try:
                result = await completed_task
                if result:
                    return True  # A single validation is enough
            except Exception as e:
                logger.error(
                    f"Error checking group membership for member {member_id}: {e}"
                )
        return False
