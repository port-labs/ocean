from typing import Dict, Any, List
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol


class Action(ABC):

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute(self, identifier: Any) -> Dict[str, Any]:
        response = await self._execute(identifier)
        return response

    @abstractmethod
    async def _execute(self, identifier: Any) -> Dict[str, Any]: ...


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


class ActionMap(Protocol):
    defaults: List[Type[Action]]
    options: List[Type[Action]]

    def merge(self, include: List[str]) -> List[Type[Action]]: ...
