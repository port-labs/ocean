from typing import Dict, Any, List, Union
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol


class Action(ABC):
    """Base interface for actions that support single execution"""

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute(self, identifier: Any) -> Dict[str, Any]:
        response = await self._execute(identifier)
        return response

    @abstractmethod
    async def _execute(self, identifier: Any) -> Dict[str, Any]: ...


class BatchAction(ABC):
    """Base interface for actions that support batch execution only"""

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]:
        """Execute action for multiple identifiers using efficient batch API"""
        return await self._execute_batch(identifiers)

    @abstractmethod
    async def _execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]: ...


class ActionMap(Protocol):
    defaults: List[Type[Union[Action, BatchAction]]]
    options: List[Type[Union[Action, BatchAction]]]

    def merge(self, include: List[str]) -> List[Type[Union[Action, BatchAction]]]: ...
