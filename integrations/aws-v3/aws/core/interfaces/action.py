from typing import Dict, Any, List
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol
from loguru import logger


class Action(ABC):

    def __init__(self, client: AioBaseClient) -> None:
        """aiobotocore's concrete clients provide methods like `get_bucket_tagging`
        at runtime, but these are not declared on `AioBaseClient`'s static types.
        Using `Any` here avoids per-call type ignores while keeping runtime behavior
        unchanged.
        """
        self.client: Any = client

    async def execute(self, identifiers: List[Any]) -> List[Dict[str, Any]]:
        logger.info(
            f"Executing {self.__class__.__name__} on {len(identifiers)} resources"
        )
        response = await self._execute(identifiers)
        return response

    @abstractmethod
    async def _execute(self, identifiers: List[Any]) -> List[Dict[str, Any]]: ...


class ActionMap(Protocol):
    defaults: List[Type[Action]]
    options: List[Type[Action]]

    def merge(self, include: List[str]) -> List[Type[Action]]:
        # Always include all defaults, and any options whose class name is in include
        logger.debug(
            f"Merging actions. Defaults: {[action.__name__ for action in self.defaults]}, Options: {[action.__name__ for action in self.options]}, Include: {include}"
        )
        merged = self.defaults + [
            action for action in self.options if action.__name__ in include
        ]
        logger.info(
            f"Effective actions selected for {type(self).__name__}: {', '.join(action.__name__ for action in merged)}"
        )
        return merged
