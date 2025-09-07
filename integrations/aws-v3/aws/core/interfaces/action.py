from typing import Dict, Any, List
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol
from loguru import logger


class Action(ABC):

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

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

    def merge(self, include: List[str]) -> List[Type[Action]]: ...
