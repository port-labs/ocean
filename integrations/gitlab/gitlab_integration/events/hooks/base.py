from abc import ABC, abstractmethod
from typing import List, Any

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
    async def _on_hook(self, group_id: str, body: dict[str, Any]) -> None:
        pass

    async def on_hook(self, event: str, group_id: str, body: dict[str, Any]) -> None:
        logger.info(f"Handling {event}")
        await self._on_hook(group_id, body)
        logger.info(f"Finished handling {event}")
