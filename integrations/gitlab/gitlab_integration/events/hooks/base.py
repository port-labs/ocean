from abc import ABC, abstractmethod
from typing import List, Any
from loguru import logger
from gitlab.v4.objects import Project

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
