from abc import ABC, abstractmethod
from typing import List, Any

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
