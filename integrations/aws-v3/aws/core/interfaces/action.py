from typing import Dict, Any, List
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol


class Action(ABC):

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute(self, identifier: Any) -> List[Dict[str, Any]]:
        response = await self._execute(identifier)
        return response

    @abstractmethod
    async def _execute(self, identifier: Any) -> List[Dict[str, Any]]: ...


class ActionMap(Protocol):
    defaults: List[Type[Action]]
    options: List[Type[Action]]

    def merge(self, include: List[str]) -> List[Type[Action]]: ...
