from abc import ABC, abstractmethod
from typing import List

from loguru import logger
from starlette.requests import Request

from gitlabapp.services.gitlab_service import GitlabService


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
    async def _on_hook(self, group_id: str, request: Request):
        pass

    async def on_hook(self, event: str, group_id: str, request: Request):
        logger.info(f"Handling {event}")
        await self._on_hook(group_id, request)
        logger.info(f"Finished handling {event}")
