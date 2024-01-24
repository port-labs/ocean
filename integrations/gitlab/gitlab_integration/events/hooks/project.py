from abc import abstractmethod
from typing import List, Any

from gitlab.v4.objects import Project
from loguru import logger

from gitlab_integration.events.hooks.base import HookHandler


class ProjectHandler(HookHandler):
    events: List[str] = []
    system_events: List[str] = []

    async def on_hook(self, event: str, body: dict[str, Any]) -> None:
        logger.info(f"Handling {event}")

        project_id = (
            body["project_id"] if "project_id" in body else body["project"]["id"]
        )
        project = self.gitlab_service.get_project(project_id)

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
