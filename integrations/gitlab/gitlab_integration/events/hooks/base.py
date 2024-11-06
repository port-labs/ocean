from abc import ABC, abstractmethod
from typing import List, Any, Optional, Dict
from loguru import logger
from gitlab.v4.objects import Project, Group
from gitlab_integration.gitlab_service import GitlabService
from gitlab_integration.utils import ObjectKind
from port_ocean.context.ocean import ocean


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
        if self.gitlab_service.should_run_for_group(gitlab_group):
            await ocean.register_raw(kind, [gitlab_group])

    async def _register_group_with_members(
        self, kind: str, gitlab_group: Group
    ) -> None:
        gitlab_group = await self.gitlab_service.enrich_group_with_members(gitlab_group)
        await self._register_group(kind, gitlab_group)
