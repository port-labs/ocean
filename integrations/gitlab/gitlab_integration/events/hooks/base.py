from abc import ABC, abstractmethod
from typing import List, Any
from loguru import logger
from gitlab.v4.objects import Project, Group
from gitlab_integration.core.async_fetcher import AsyncFetcher
from gitlab_integration.gitlab_service import GitlabService


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
            await self._on_hook(body, project)
            logger.info(f"Finished handling {event}")
        else:
            logger.info(
                f"Project {body['project']['id']} was filtered for event {event}. Skipping..."
            )

    @abstractmethod
    async def _on_hook(self, body: dict[str, Any], gitlab_project: Project) -> None:
        pass


class GroupHandler(HookHandler):
    async def on_hook(self, event: str, body: dict[str, Any]) -> None:
        event_name = body["event_name"]
        group_id = body.get("group_id", body.get("group", {}).get("id"))
        logger.info(f"Handling {event_name} for {event} and group {group_id}")
        group = await self.gitlab_service.get_group(group_id)
        group_path = body.get('full_path',body.get('group_path'))
        logger.info(f"Handling hook {event} for group {group_path}")
        await self._on_hook(body, group)
        logger.info(f"Finished handling {event} for group {group_path}")

    @abstractmethod
    async def _on_hook(self, body: dict[str, Any], gitlab_group: Group) -> None:
        pass
