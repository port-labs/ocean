from typing import Dict, Any
from abc import ABC, abstractmethod
from aiobotocore.client import AioBaseClient


class IAction(ABC):
    name: str

    def __init__(self, client: AioBaseClient) -> None:
        self.client: AioBaseClient = client

    async def execute(self, identifier: str) -> Dict[str, Any]:
        response = await self._execute(identifier)
        return response

    @abstractmethod
    async def _execute(self, identifier: str) -> Dict[str, Any]: ...
