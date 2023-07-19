from abc import ABC, abstractmethod
from typing import List, Any

from gitlab.v4.objects import Project
from loguru import logger

from gitlab_integration.gitlab_service import GitlabService


class HookHandler(ABC):
    def __init__(
        self,
        gitlab_service: GitlabService,
    ):
        self.gitlab_service = gitlab_service

    @property
    @abstractmethod
    def events(self) -> List[str]:
        return []

    @abstractmethod
    async def _on_hook(
        self, group_id: str, body: dict[str, Any], gitlab_project: Project
    ) -> None:
        pass

    async def on_hook(self, event: str, group_id: str, body: dict[str, Any]) -> None:
        logger.info(f"Handling {event}")
        project = self.gitlab_service.get_project(body["project"]["id"])

        if project is not None:
            await self._on_hook(group_id, body, project)
            logger.info(f"Finished handling {event}")
        else:
            logger.info(
                f"Project {body['project']['id']} was filtered for event {event}. Skipping..."
            )
