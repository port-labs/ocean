from typing import Dict, Any, List
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol


class IAction(ABC):
    name: str

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute(self, identifier: str) -> Dict[str, Any]:
        response = await self._execute(identifier)
        return response

    @abstractmethod
    async def _execute(self, identifier: str) -> Dict[str, Any]: ...


class IActionMap(Protocol):
    defaults: List[Type[IAction]]
    optional: List[Type[IAction]]

    def merge(self, include: List[str]) -> List[Type[IAction]]: ...
