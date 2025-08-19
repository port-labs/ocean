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


class DataAction(Action):
    """Actions that transform/derive data (no API calls) - always fast"""

    async def _execute(self, identifier: Any) -> Dict[str, Any]:
        return await self._transform_data(identifier)

    @abstractmethod
    async def _transform_data(self, identifier: Any) -> Dict[str, Any]: ...


class APIAction(Action):
    """Actions that make single API calls to external services"""

    @abstractmethod
    async def _execute(self, identifier: Any) -> Dict[str, Any]: ...


class BatchAPIAction(Action):
    """Actions that support efficient batch API calls"""

    async def execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]:
        """Execute action for multiple identifiers using efficient batch API"""
        return await self._execute_batch(identifiers)

    @abstractmethod
    async def _execute(self, identifier: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def _execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]: ...


class ActionMap(Protocol):
    defaults: List[Type[Action]]
    options: List[Type[Action]]

    def merge(self, include: List[str]) -> List[Type[Action]]: ...
