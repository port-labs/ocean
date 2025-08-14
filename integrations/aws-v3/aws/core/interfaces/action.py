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


class IBatchAction(IAction):
    """Interface for actions that support batch execution"""

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]:
        """Execute action for multiple identifiers in batch"""
        response = await self._execute_batch(identifiers)
        return response

    @abstractmethod
    async def _execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]: ...

    @abstractmethod
    async def _execute(self, identifier: str) -> Dict[str, Any]: ...


class IActionMap(Protocol):
    defaults: List[Type[IAction]]
    optional: List[Type[IAction]]

    def merge(self, include: List[str]) -> List[Type[IAction]]: ...
