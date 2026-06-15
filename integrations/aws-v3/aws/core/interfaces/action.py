from dataclasses import dataclass
from typing import Dict, Any, List
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol
from loguru import logger


@dataclass
class BaseActionInput:
    items: list[Any]


type ActionInputType = list[Any] | BaseActionInput


class Action[ActionInput: ActionInputType](ABC):

    def __init__(self, client: AioBaseClient) -> None:
        """aiobotocore's concrete clients provide methods like `get_bucket_tagging`
        at runtime, but these are not declared on `AioBaseClient`'s static types.
        Using `Any` here avoids per-call type ignores while keeping runtime behavior
        unchanged.
        """
        self.client: Any = client

    async def execute(self, identifiers: ActionInput) -> List[Dict[str, Any]]:
        if isinstance(identifiers, list):
            count = len(identifiers)
        elif isinstance(identifiers, BaseActionInput):
            count = len(identifiers.items)
        else:
            count = "unknown"

        logger.info(f"Executing {self.__class__.__name__} on {count} resources")
        response = await self._execute(identifiers)
        logger.info(f"{self.__class__.__name__} fetched {len(response)} resources")
        return response

    @abstractmethod
    async def _execute(self, identifiers: ActionInput) -> List[Dict[str, Any]]: ...


class ActionMap[ActionInput: ActionInputType](Protocol):
    defaults: List[Type[Action[ActionInput]]]
    options: List[Type[Action[ActionInput]]]

    def merge(self, include: List[str]) -> List[Type[Action[ActionInput]]]:
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
