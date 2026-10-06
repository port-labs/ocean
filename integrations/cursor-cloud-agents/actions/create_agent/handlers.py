from __future__ import annotations

from abc import ABC, abstractmethod

from actions.abstract_executor import AbstractCursorExecutor
from actions.create_agent.context import (
    API_VERSION_V0,
    API_VERSION_V1,
    CreateAgentContext,
)


class CreateAgentHandler(ABC):
    @abstractmethod
    async def execute(
        self, executor: AbstractCursorExecutor, ctx: CreateAgentContext
    ) -> None:
        raise NotImplementedError


_HANDLERS: dict[str, CreateAgentHandler] | None = None


def get_handler(api_version: str) -> CreateAgentHandler:
    global _HANDLERS
    if _HANDLERS is None:
        from actions.create_agent.v0_handler import CreateAgentV0Handler
        from actions.create_agent.v1_handler import CreateAgentV1Handler

        _HANDLERS = {
            API_VERSION_V0: CreateAgentV0Handler(),
            API_VERSION_V1: CreateAgentV1Handler(),
        }
    return _HANDLERS[api_version]
