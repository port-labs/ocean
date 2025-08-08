from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, TYPE_CHECKING, Dict
from aiobotocore.session import AioSession
from aws.core.helpers.types import SupportedServices

if TYPE_CHECKING:
    from aiobotocore.client import AioBaseClient


class IResourceExporter(ABC):

    SERVICE_NAME: SupportedServices

    def __init__(self, session: AioSession) -> None:
        self.session = session
        self._client: AioBaseClient | None = None

    @abstractmethod
    async def get_resource(self, options: Any) -> Dict[str, Any]:
        """Fetch a single resource's detailed data by ID (e.g., ARN, URL, Name)."""
        ...

    @abstractmethod
    def get_paginated_resources(
        self, options: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated number of pages of resources."""
        ...
