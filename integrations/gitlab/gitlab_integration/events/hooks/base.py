from abc import ABC, abstractmethod
from typing import List, Any, Dict, Optional
import typing
from loguru import logger
from gitlab.v4.objects import Project, Group
from gitlab.base import RESTObject
from gitlab_integration.gitlab_service import GitlabService
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from gitlab_integration.git_integration import (
    GitlabPortAppConfig,
    GitlabMemberSelector,
)


class HookHandler(ABC):
    events: List[str] = []
    system_events: List[str] = []

    def __init__(
        self,
        gitlab_service: GitlabService,
    ):
        self.gitlab_service = gitlab_service

    @abstractmethod
    async def on_hook(self, event: str, body: dict[str, Any]) -> None:
        pass

    async def _register_object_with_members(self, kind: str, gitlab_object: RESTObject):
        resource_configs = typing.cast(
            GitlabPortAppConfig, event.port_app_config
        ).resources

        matching_resource_configs = [
            resource_config
            for resource_config in resource_configs
            if (
                resource_config.kind == kind
                and isinstance(resource_config.selector, GitlabMemberSelector)
            )
        ]

        if not matching_resource_configs:
            logger.info(
                "Resource not found in port app config, update port app config to include the resource type"
            )
            return

        for resource_config in matching_resource_configs:
            include_bot_members = resource_config.selector.include_bot_members
            include_inherited_members = (
                resource_config.selector.include_inherited_members
            )

            object_result: RESTObject = (
                await self.gitlab_service.enrich_object_with_members(
                    gitlab_object,
                    include_bot_members,
                    include_inherited_members,
                )
            )
            await ocean.register_raw(resource_config.kind, [object_result.asdict()])


class ProjectHandler(HookHandler):
    async def on_hook(self, event: str, body: dict[str, Any]) -> None:
        logger.info(f"Handling {event}")

        project_id = (
            body["project_id"] if "project_id" in body else body["project"]["id"]
        )
        project = await self.gitlab_service.get_project(project_id)

        if project:
            logger.info(
                f"Handling hook {event} for project {project.path_with_namespace}"
            )
            try:
                await self._on_hook(body, project)
                logger.info(f"Finished handling {event}")
            except Exception as e:
                logger.error(
                    f"Error handling hook {event} for project {project.path_with_namespace}. Error: {e}"
                )
        else:
            logger.info(
                f"Project {body['project']['id']} was filtered for event {event}. Skipping..."
            )

    @abstractmethod
    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        pass


class GroupHandler(HookHandler):
    async def on_hook(self, event: str, body: dict[str, Any]) -> None:
        logger.info(f"Handling {event}")

        group_id = body.get("group_id", body.get("group", {}).get("id"))
        group = await self.gitlab_service.get_group(group_id)
        await self._on_hook(body, group)
        group_path = body.get("full_path", body.get("group_path"))
        logger.info(f"Finished handling {event} for group {group_path}")

    @abstractmethod
    async def _on_hook(
        self, body: dict[str, Any], gitlab_group: Optional[Group]
    ) -> None:
        pass

    async def _register_group(self, kind: str, gitlab_group: Dict[str, Any]) -> None:
        await ocean.register_raw(kind, [gitlab_group])
