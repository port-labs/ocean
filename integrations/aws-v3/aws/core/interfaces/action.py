from typing import Dict, Any, List, Union, Protocol
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient
from typing import Type, Protocol
import asyncio


class Action(ABC):
    """Base interface for actions that support single execution"""

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute(self, identifier: Any) -> Dict[str, Any]:
        response = await self._execute(identifier)
        return response

    async def execute_for_identifiers(
        self, identifiers: List[str]
    ) -> List[Dict[str, Any]]:
        """Execute action for multiple identifiers by calling execute for each one."""
        return await asyncio.gather(
            *[self.execute(identifier) for identifier in identifiers]
        )

    @abstractmethod
    async def _execute(self, identifier: Any) -> Dict[str, Any]: ...


class BatchAction(ABC):
    """Base interface for actions that support batch execution only"""

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]:
        """Execute action for multiple identifiers using efficient batch API"""
        return await self._execute_batch(identifiers)

    async def execute_for_identifiers(
        self, identifiers: List[str]
    ) -> List[Dict[str, Any]]:
        """Execute action for multiple identifiers using efficient batch API."""
        return await self.execute_batch(identifiers)

    @abstractmethod
    async def _execute_batch(self, identifiers: List[str]) -> List[Dict[str, Any]]: ...


class SingleActionMap(Protocol):
    """Protocol for action maps that only contain Action types for single resource operations."""

    @property
    def defaults(self) -> List[Type[Action]]: ...

    @property
    def options(self) -> List[Type[Action]]: ...

    def merge(self, include: List[str]) -> List[Type[Action]]: ...


class BatchActionMap(Protocol):
    """Protocol for action maps that only contain BatchAction types for batch operations."""

    @property
    def defaults(self) -> List[Type[BatchAction]]: ...

    @property
    def options(self) -> List[Type[BatchAction]]: ...

    def merge(self, include: List[str]) -> List[Type[BatchAction]]: ...
